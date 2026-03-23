"""
TutorSession — core logic for `locus tutor`.

Handles file validation, prompt building, line_cache, and background
workers for file summary (Worker A) and prefetch (Worker B).
Workers run as threading.Thread instances (not Textual @work).
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

# Maximum file size accepted by locus tutor
_MAX_LINES = 500
_MAX_BYTES = 20 * 1024  # 20 KB


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
                f"File too large: {len(raw) / 1024:.0f} KB (max 20 KB). "
                "Large-file tutoring is not supported in v0.1.0."
            )

        lines = content.splitlines()

        if len(lines) > _MAX_LINES:
            raise ValueError(
                f"File too long: {len(lines)} lines (max {_MAX_LINES}). "
                "Large-file tutoring is not supported in v0.1.0."
            )

        return content, lines

    # ------------------------------------------------------------------ #
    # Cursor tracking (called by TutorApp on every line change)
    # ------------------------------------------------------------------ #

    def set_cursor(self, line_num: int) -> None:
        """Update cursor position so Worker B knows when to resume."""
        self._cursor_line = line_num

    # ------------------------------------------------------------------ #
    # Worker A — file summary (placeholder, started post-validation)
    # ------------------------------------------------------------------ #

    def _start_worker_a(self) -> None:
        """Start Worker A in a background thread (no-op until LLM is wired)."""
        t = threading.Thread(target=self._worker_a, daemon=True)
        t.start()

    def _worker_a(self) -> None:
        """Worker A: generate file summary via LLM (stub)."""
        # Full implementation added in a later task when inference is wired.
        self._summary_ready.set()
        if self._on_summary_ready_cb is not None:
            self._on_summary_ready_cb()

    # ------------------------------------------------------------------ #
    # Prompt builders
    # ------------------------------------------------------------------ #

    def build_summary_prompt(self) -> str:
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
            f"{self._content}"
        )

    def build_line_prompt(self, line_num: int) -> str:
        # line_num is 1-indexed
        line_content = self.lines[line_num - 1] if 1 <= line_num <= len(self.lines) else ""
        return (
            "You are a code tutor helping a developer understand a file line by line.\n\n"
            f"FILE SUMMARY:\n{self.file_summary}\n\n"
            f"FULL FILE ({self.file_path.name}):\n"
            "---\n"
            f"{self._content}\n"
            "---\n\n"
            f"The developer is currently on line {line_num}:\n"
            f">>> {line_content}\n\n"
            "Explain this line in plain language. If the line is part of a larger logical block "
            "(a function, class, loop, condition), also explain its role in that context. "
            "Be concise — 2-5 sentences."
        )
