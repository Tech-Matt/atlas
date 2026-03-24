"""
TutorSession — core logic for `locus tutor`.

Handles file validation, prompt building, line_cache, and background
workers for file summary (Worker A) and prefetch (Worker B).
Workers run as threading.Thread instances (not Textual @work).
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path

# Maximum file size accepted by locus tutor
_MAX_BYTES = 500 * 1024  # 500 KB


class TutorSession:
    """
    Owns the tutoring session state for a single file.

    Args:
        file_path:     Path to the file to tutor.
        n_gpu_layers:  -1 = full GPU offload, 0 = CPU only.
        model_path:    Path to the GGUF model file.
        on_summary_ready: Callback fired (from Worker A's thread) when the
                          file summary is available. Intended for TutorApp to
                          post a SummaryReady message via app.call_from_thread.
        _skip_workers: Internal flag for tests — skips starting Worker A/B.
    """

    def __init__(
        self,
        file_path: Path,
        n_gpu_layers: int,
        model_path: Path | None = None,
        on_summary_ready: Callable[[], None] | None = None,
        _skip_workers: bool = False,
    ) -> None:
        self.file_path = Path(file_path).expanduser().resolve()
        self.n_gpu_layers = n_gpu_layers
        self.model_path = model_path
        self._on_summary_ready_cb = on_summary_ready

        # Validate and load file
        self._content, self.lines = self._load_and_validate(self.file_path)

        # Session state
        self.file_summary: str | None = None
        self.line_cache: dict[int, str] = {}
        self._cursor_line: int = 1
        self._summary_ready = threading.Event()
        self._llm_lock = threading.Lock()
        self._cache_lock = threading.Lock()

        if not _skip_workers:
            self._start_worker_a()

    # ------------------------------------------------------------------ #
    # File loading
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_and_validate(path: Path) -> tuple[str, list[str]]:
        if not path.exists():
            raise ValueError(f"File does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        raw = path.read_bytes()

        # Reject binary files
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = raw.decode("latin-1")
                # Latin-1 always decodes, so check for null bytes as a binary signal
                if "\x00" in content:
                    raise ValueError(f"File appears to be binary: {path}")
            except UnicodeDecodeError:
                raise ValueError(f"File appears to be binary (not UTF-8): {path}")

        if len(raw) > _MAX_BYTES:
            raise ValueError(
                f"File too large: {len(raw) / 1024:.0f} KB (max 500 KB)."
            )

        lines = content.splitlines()

        return content, lines

    # ------------------------------------------------------------------ #
    # Cursor tracking (called by TutorApp on every line change)
    # ------------------------------------------------------------------ #

    def set_cursor(self, line_num: int) -> None:
        """Update cursor position so Worker B knows when to resume."""
        self._cursor_line = line_num

    # ------------------------------------------------------------------ #
    # Worker A — file summary (runs in background thread)
    # ------------------------------------------------------------------ #

    def _start_worker_a(self) -> None:
        """Start Worker A in a background thread."""
        t = threading.Thread(target=self._worker_a_body, daemon=True)
        t.start()

    def _worker_a_body(self) -> None:
        self._run_worker_a(
            llm_fn=self._call_llm,
            on_done=self._on_summary_ready,
        )

    def _run_worker_a(
        self,
        llm_fn: Callable[[str], str],
        on_done: Callable[[], None],
    ) -> None:
        """Generate file summary synchronously. Called by the Worker A thread."""
        self.file_summary = llm_fn(self.build_summary_prompt())
        self._summary_ready.set()
        on_done()

    def _on_summary_ready(self) -> None:
        """Called by Worker A when the summary is ready. Fires the app callback and starts Worker B."""
        if self._on_summary_ready_cb:
            self._on_summary_ready_cb()
        self._start_worker_b()

    # ------------------------------------------------------------------ #
    # Worker B — prefetch queue (runs in background thread)
    # ------------------------------------------------------------------ #

    _PREFETCH_AHEAD = 20  # pause when cached_line > cursor_line + this
    _WINDOW = 40  # lines of context on each side of the cursor
    _SUMMARY_SAMPLE_THRESHOLD = 400

    def _start_worker_b(self) -> None:
        """Start Worker B from the current cursor position."""
        self._worker_b_stop = threading.Event()
        t = threading.Thread(
            target=self._run_worker_b,
            kwargs={
                "start_line": self._cursor_line,
                "llm_fn": self._call_llm,
                "stop_event": self._worker_b_stop,
            },
            daemon=True,
        )
        t.start()

    def _run_worker_b(
        self,
        start_line: int,
        llm_fn: Callable[[str], str],
        stop_event: threading.Event,
    ) -> None:
        """Prefetch explanations from start_line to end of file."""
        for line_num in range(start_line, len(self.lines) + 1):
            if stop_event.is_set():
                return
            # Pause if too far ahead of cursor
            while line_num > self._cursor_line + self._PREFETCH_AHEAD:
                if stop_event.is_set():
                    return
                time.sleep(0.1)
            if line_num not in self.line_cache:
                explanation = llm_fn(self.build_line_prompt(line_num))
                with self._cache_lock:
                    self.line_cache[line_num] = explanation

    # ------------------------------------------------------------------ #
    # Prompt builders
    # ------------------------------------------------------------------ #

    def build_summary_prompt(self) -> str:
        total = len(self.lines)

        if total <= self._SUMMARY_SAMPLE_THRESHOLD:
            file_content = self._content
        else:
            head = self.lines[0:300]
            mid = total // 2
            mid_start = max(300, mid - 50)
            mid_end = min(total - 100, mid_start + 100)

            sections: list[str] = ["\n".join(head)]

            mid_included = False
            if mid_start < mid_end:
                omitted_before = mid_start - 300
                if omitted_before > 0:
                    sections.append(f"[... {omitted_before} lines omitted ...]")
                    sections.append("\n".join(self.lines[mid_start:mid_end]))
                    mid_included = True

            tail_start_line = mid_end if mid_included else 300
            omitted_before_tail = total - 100 - tail_start_line
            sections.append(f"[... {omitted_before_tail} lines omitted ...]")
            sections.append("\n".join(self.lines[-100:]))

            file_content = "\n".join(sections)

        return (
            "You are a code tutor. Read the following file and write a structured summary "
            "for a developer who is about to read it line by line.\n\n"
            "Cover:\n"
            "1. What this file does overall (1-2 sentences)\n"
            "2. Its key components — list the main classes and functions with a one-line description of each\n"
            "3. Any important patterns, conventions, or design decisions a reader should know before diving in\n\n"
            "Be concise but thorough. Target 150-250 words.\n\n"
            f"FILE: {self.file_path.name}\n"
            "---\n"
            f"{file_content}"
        )

    # ------------------------------------------------------------------ #
    # line_cache interface
    # ------------------------------------------------------------------ #

    def get_explanation(self, line_num: int) -> str | None:
        """Return the cached explanation for line_num, or None on a miss."""
        return self.line_cache.get(line_num)

    def request_explanation(
        self,
        line_num: int,
        _llm_fn: Callable[[str], str] | None = None,
    ) -> str:
        """
        Return the explanation for line_num, generating it if not cached.

        _llm_fn: injectable for tests. Production callers omit this and
                 the real LLM is used via _call_llm().
        """
        if line_num in self.line_cache:
            return self.line_cache[line_num]
        llm = _llm_fn or self._call_llm
        explanation = llm(self.build_line_prompt(line_num))
        with self._cache_lock:
            self.line_cache[line_num] = explanation
        return explanation

    def _get_llm(self):
        """Return the shared Llama instance, loading it once on first call."""
        if not hasattr(self, "_llm_instance") or self._llm_instance is None:
            import os
            from llama_cpp import Llama  # type: ignore[import]
            
            # Suppress C-level stderr logging (fd 2) that circumvents Textual 
            # and breaks the TUI rendering and terminal state.
            try:
                old_stderr = os.dup(2)
                devnull = os.open(os.devnull, os.O_WRONLY)
                os.dup2(devnull, 2)
            except Exception:
                old_stderr = None
                
            try:
                self._llm_instance = Llama(
                    model_path=str(self.model_path),
                    n_gpu_layers=self.n_gpu_layers,
                    n_ctx=8192,
                    verbose=False,
                    chat_format="chatml",
                )
            finally:
                if old_stderr is not None:
                    os.dup2(old_stderr, 2)
                    os.close(old_stderr)
                    os.close(devnull)
        return self._llm_instance

    def _call_llm(self, prompt: str) -> str:
        """Call the local LLM with a single prompt and return the full response."""
        with self._llm_lock:
            llm = self._get_llm()
            result = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            return result["choices"][0]["message"]["content"].strip()

    def stream_explanation(
        self,
        line_num: int,
        on_token: Callable[[str], None],
        on_done: Callable[[str], None],
        _stream_fn: Callable[[str, Callable[[str], None]], str] | None = None,
    ) -> None:
        """
        Stream an explanation for line_num, calling on_token for each token
        and on_done(full_text) when complete. Caches the result in line_cache.

        _stream_fn: injectable for tests. Signature: (prompt, on_token_fn) -> full_text.
        """
        if line_num in self.line_cache:
            on_done(self.line_cache[line_num])
            return

        prompt = self.build_line_prompt(line_num)

        if _stream_fn is not None:
            full_text = _stream_fn(prompt, on_token)
        else:
            full_text_parts: list[str] = []
            with self._llm_lock:
                llm = self._get_llm()
                for chunk in llm.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.3,
                    stream=True,
                ):
                    token: str = chunk["choices"][0]["delta"].get("content", "")
                    if token:
                        full_text_parts.append(token)
                        on_token(token)
            full_text = "".join(full_text_parts)

        with self._cache_lock:
            self.line_cache[line_num] = full_text

        on_done(full_text)

    def build_line_prompt(self, line_num: int) -> str:
        total = len(self.lines)
        start = max(1, line_num - self._WINDOW)
        end = min(total, line_num + self._WINDOW)
        window_lines = "\n".join(self.lines[start - 1 : end])
        line_content = self.lines[line_num - 1] if 1 <= line_num <= total else ""
        summary = self.file_summary or "(summary not yet available)"

        return (
            "You are a code tutor helping a developer understand a file line by line.\n\n"
            f"FILE SUMMARY:\n{summary}\n\n"
            f"EXCERPT (Lines {start}–{end} of {total}):\n"
            "---\n"
            f"{window_lines}\n"
            "---\n\n"
            f"The developer is currently on line {line_num}:\n"
            f">>> {line_content}\n\n"
            "Explain this line in plain language. If the line is part of a larger logical block "
            "(a function, class, loop, condition), also explain its role in that context. "
            "Be concise — 2-5 sentences."
        )
