# locus tutor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `locus tutor <file>` — a Textual TUI that walks a developer through a file line-by-line with on-demand AI explanations, powered by a local LLM.

**Architecture:** `TutorSession` (plain Python class in `core/tutor.py`) owns file validation, prompt building, the `line_cache`, and two background `threading.Thread` workers (A: file summary, B: prefetch queue). `TutorApp` (Textual app in `ui/tutor_app.py`) renders the side-by-side split layout, handles keyboard input, and communicates with `TutorSession` via a `SummaryReady` message and Textual `@work(thread=True)` workers for on-demand generation. `cmd_tutor` in `main.py` handles pre-TUI validation and provisioning, then launches `TutorApp`.

**Tech Stack:** Python 3.11+, Textual, Rich, llama-cpp-python, threading, argparse

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/locus_cli/core/tutor.py` | File validation, prompt builders, `line_cache`, Worker A & B threads |
| Create | `src/locus_cli/ui/tutor_app.py` | Textual TUI — layout, keyboard handling, panel state machine |
| Modify | `src/locus_cli/main.py` | Add `cmd_tutor()` and wire `locus tutor <file>` subcommand |
| Create | `tests/test_tutor.py` | Unit tests for `TutorSession` logic (no LLM, no Textual) |

---

## Task 1: Feature Branch

**Files:** none

- [ ] **Step 1: Create and switch to the feature branch**

```bash
git checkout -b feature/tutor-command
```

- [ ] **Step 2: Verify you're on the right branch**

```bash
git branch --show-current
```

Expected output: `feature/tutor-command`

---

## Task 2: TutorSession — File Validation

**Files:**
- Create: `src/locus_cli/core/tutor.py`
- Create: `tests/test_tutor.py`

This task covers the public guard: `cmd_tutor` calls `TutorSession(file_path, n_gpu_layers)` which validates the file before anything else runs.

- [ ] **Step 1: Write failing tests for file validation**

Create `tests/test_tutor.py`:

```python
"""Tests for core/tutor.py — no LLM required."""
from __future__ import annotations
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# TutorSession — file validation
# ---------------------------------------------------------------------------

def test_tutor_session_raises_on_missing_file(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    with pytest.raises(ValueError, match="does not exist"):
        TutorSession(tmp_path / "missing.py", n_gpu_layers=0)


def test_tutor_session_raises_on_directory(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    with pytest.raises(ValueError, match="not a file"):
        TutorSession(tmp_path, n_gpu_layers=0)


def test_tutor_session_raises_on_binary_file(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    with pytest.raises(ValueError, match="binary"):
        TutorSession(binary, n_gpu_layers=0)


def test_tutor_session_raises_when_file_too_long(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    big = tmp_path / "big.py"
    big.write_text("\n".join(f"x = {i}" for i in range(501)))
    with pytest.raises(ValueError, match="501 lines"):
        TutorSession(big, n_gpu_layers=0)


def test_tutor_session_raises_when_file_too_large(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    big = tmp_path / "big.py"
    # Write just over 20 KB
    big.write_bytes(b"x = 1\n" * 3500)
    with pytest.raises(ValueError, match="20 KB"):
        TutorSession(big, n_gpu_layers=0)


def test_tutor_session_accepts_valid_python_file(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "hello.py"
    src.write_text("def hello():\n    return 'hi'\n")
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    assert session.lines == ["def hello():", "    return 'hi'", ""]
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `TutorSession` does not exist yet.

- [ ] **Step 3: Create `src/locus_cli/core/tutor.py` with file validation**

```python
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

        lines = content.splitlines()

        if len(lines) > _MAX_LINES:
            raise ValueError(
                f"File too long: {len(lines)} lines (max {_MAX_LINES}). "
                "Large-file tutoring is not supported in v0.1.0."
            )
        if len(raw) > _MAX_BYTES:
            raise ValueError(
                f"File too large: {len(raw) / 1024:.0f} KB (max 20 KB). "
                "Large-file tutoring is not supported in v0.1.0."
            )

        return content, lines

    # ------------------------------------------------------------------ #
    # Cursor tracking (called by TutorApp on every line change)
    # ------------------------------------------------------------------ #

    def set_cursor(self, line_num: int) -> None:
        """Update cursor position so Worker B knows when to resume."""
        self._cursor_line = line_num
```

- [ ] **Step 4: Run tests — verify file-validation tests pass**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/locus_cli/core/tutor.py tests/test_tutor.py
git commit -m "feat: add TutorSession with file validation"
```

---

## Task 3: TutorSession — Prompt Builders

**Files:**
- Modify: `src/locus_cli/core/tutor.py`
- Modify: `tests/test_tutor.py`

The two prompts (file summary + per-line explanation) are pure string functions — easy to test without any LLM.

- [ ] **Step 1: Write failing tests for prompt builders**

Append to `tests/test_tutor.py`:

```python
# ---------------------------------------------------------------------------
# TutorSession — prompt builders
# ---------------------------------------------------------------------------

def _make_session(tmp_path: Path, content: str = "def foo():\n    return 1\n") -> object:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "sample.py"
    src.write_text(content)
    return TutorSession(src, n_gpu_layers=0, _skip_workers=True)


def test_build_summary_prompt_contains_filename(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    prompt = session.build_summary_prompt()
    assert "sample.py" in prompt


def test_build_summary_prompt_contains_file_content(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    prompt = session.build_summary_prompt()
    assert "def foo():" in prompt


def test_build_line_prompt_contains_line_content(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "This file defines foo."
    prompt = session.build_line_prompt(line_num=1)
    assert "def foo():" in prompt


def test_build_line_prompt_contains_summary(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "This file defines foo."
    prompt = session.build_line_prompt(line_num=1)
    assert "This file defines foo." in prompt


def test_build_line_prompt_contains_line_number(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"
    prompt = session.build_line_prompt(line_num=2)
    assert "2" in prompt


def test_build_line_prompt_marks_current_line(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"
    prompt = session.build_line_prompt(line_num=1)
    assert ">>>" in prompt
```

- [ ] **Step 2: Run — verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v -k "prompt"
```

Expected: `AttributeError` — methods not defined yet.

- [ ] **Step 3: Add prompt builders to `TutorSession`**

Add these methods inside the `TutorSession` class in `tutor.py`:

```python
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
```

- [ ] **Step 4: Run — verify prompt tests pass**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/locus_cli/core/tutor.py tests/test_tutor.py
git commit -m "feat: add prompt builders to TutorSession"
```

---

## Task 4: TutorSession — line_cache Interface

**Files:**
- Modify: `src/locus_cli/core/tutor.py`
- Modify: `tests/test_tutor.py`

Tests for `get_explanation` (cache probe) and `request_explanation` (blocking generation). The LLM call is injected via a parameter so tests stay fast.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_tutor.py`:

```python
# ---------------------------------------------------------------------------
# TutorSession — line_cache interface
# ---------------------------------------------------------------------------

def test_get_explanation_returns_none_on_cache_miss(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    assert session.get_explanation(1) is None


def test_get_explanation_returns_cached_value(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.line_cache[1] = "This defines foo."
    assert session.get_explanation(1) == "This defines foo."


def test_request_explanation_uses_injected_llm(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"

    def fake_llm(prompt: str) -> str:
        return "Fake explanation."

    result = session.request_explanation(1, _llm_fn=fake_llm)
    assert result == "Fake explanation."


def test_request_explanation_caches_result(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"

    session.request_explanation(1, _llm_fn=lambda p: "cached!")
    assert session.get_explanation(1) == "cached!"


def test_request_explanation_does_not_regenerate_cached(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"
    session.line_cache[1] = "already cached"

    call_count = {"n": 0}
    def counting_llm(prompt: str) -> str:
        call_count["n"] += 1
        return "new value"

    result = session.request_explanation(1, _llm_fn=counting_llm)
    assert result == "already cached"
    assert call_count["n"] == 0
```

- [ ] **Step 2: Run — verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v -k "explanation"
```

Expected: `AttributeError` — methods not defined.

- [ ] **Step 3: Add cache methods to `TutorSession`**

```python
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
        self.line_cache[line_num] = explanation
        return explanation

    def _get_llm(self):
        """Return the shared Llama instance, loading it once on first call."""
        if not hasattr(self, "_llm_instance") or self._llm_instance is None:
            from llama_cpp import Llama  # type: ignore[import]
            self._llm_instance = Llama(
                model_path=str(self.model_path),
                n_gpu_layers=self.n_gpu_layers,
                n_ctx=8192,
                verbose=False,
                chat_format="chatml",
            )
        return self._llm_instance

    def _call_llm(self, prompt: str) -> str:
        """Call the local LLM with a single prompt and return the full response."""
        llm = self._get_llm()
        result = llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return result["choices"][0]["message"]["content"].strip()
```

- [ ] **Step 4: Run — verify tests pass**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/locus_cli/core/tutor.py tests/test_tutor.py
git commit -m "feat: add line_cache get/request_explanation to TutorSession"
```

---

## Task 5: TutorSession — Worker A (File Summary)

**Files:**
- Modify: `src/locus_cli/core/tutor.py`
- Modify: `tests/test_tutor.py`

Worker A generates the file summary in a background `threading.Thread`. It fires `on_summary_ready` when done.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_tutor.py`:

```python
# ---------------------------------------------------------------------------
# TutorSession — Worker A (file summary)
# ---------------------------------------------------------------------------

def test_on_summary_ready_fires_after_summary_set(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "a.py"
    src.write_text("x = 1\n")

    fired = threading.Event()

    def fake_llm(prompt: str) -> str:
        return "A summary."

    session = TutorSession(
        src,
        n_gpu_layers=0,
        _skip_workers=True,
    )
    session._run_worker_a(llm_fn=fake_llm, on_done=lambda: fired.set())
    assert fired.wait(timeout=2), "on_summary_ready was never called"
    assert session.file_summary == "A summary."


def test_summary_ready_event_is_set_after_worker_a(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "a.py"
    src.write_text("x = 1\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session._run_worker_a(llm_fn=lambda p: "summary", on_done=lambda: None)
    assert session._summary_ready.is_set()
```

Note: add `import threading` at the top of `tests/test_tutor.py`.

- [ ] **Step 2: Run — verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v -k "worker_a or summary"
```

- [ ] **Step 3: Add Worker A to `TutorSession`**

```python
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
```

- [ ] **Step 4: Run — verify tests pass**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/locus_cli/core/tutor.py tests/test_tutor.py
git commit -m "feat: add Worker A (file summary) to TutorSession"
```

---

## Task 6: TutorSession — Worker B (Prefetch Queue)

**Files:**
- Modify: `src/locus_cli/core/tutor.py`
- Modify: `tests/test_tutor.py`

Worker B prefetches explanations line-by-line, pausing when it gets more than 20 lines ahead of the cursor.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_tutor.py`:

```python
# ---------------------------------------------------------------------------
# TutorSession — Worker B (prefetch queue)
# ---------------------------------------------------------------------------

def test_worker_b_populates_cache(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "b.py"
    src.write_text("a = 1\nb = 2\nc = 3\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"
    session._cursor_line = 1

    session._run_worker_b(
        start_line=1,
        llm_fn=lambda p: "explanation",
        stop_event=threading.Event(),
    )

    # All three lines should be cached
    assert session.get_explanation(1) == "explanation"
    assert session.get_explanation(2) == "explanation"
    assert session.get_explanation(3) == "explanation"


def test_worker_b_skips_already_cached_lines(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "b.py"
    src.write_text("a = 1\nb = 2\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"
    session.line_cache[1] = "pre-cached"
    session._cursor_line = 1

    call_count = {"n": 0}
    def counting_llm(p: str) -> str:
        call_count["n"] += 1
        return "new"

    session._run_worker_b(
        start_line=1,
        llm_fn=counting_llm,
        stop_event=threading.Event(),
    )
    # Line 1 was already cached; only line 2 should trigger LLM
    assert call_count["n"] == 1
    assert session.get_explanation(1) == "pre-cached"


def test_worker_b_respects_stop_event(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "b.py"
    src.write_text("\n".join(f"x = {i}" for i in range(50)) + "\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"
    session._cursor_line = 1

    stop = threading.Event()
    stop.set()  # pre-set: worker should exit immediately

    session._run_worker_b(start_line=1, llm_fn=lambda p: "x", stop_event=stop)
    # Cache should be empty or at most 1 entry — worker exited early
    assert len(session.line_cache) <= 1
```

- [ ] **Step 2: Run — verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v -k "worker_b"
```

- [ ] **Step 3: Add Worker B to `TutorSession`**

```python
    # ------------------------------------------------------------------ #
    # Worker B — prefetch queue (runs in background thread)
    # ------------------------------------------------------------------ #

    _PREFETCH_AHEAD = 20  # pause when cached_line > cursor_line + this

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
                self.line_cache[line_num] = explanation
```

- [ ] **Step 4: Run — all tests pass**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/locus_cli/core/tutor.py tests/test_tutor.py
git commit -m "feat: add Worker B (prefetch queue) to TutorSession"
```

---

## Task 7: cmd_tutor + Argparse Wiring

**Files:**
- Modify: `src/locus_cli/main.py`
- Modify: `tests/test_tutor.py`

Wire up the `locus tutor <file>` subcommand. Pre-flight validation, provisioning, then launch TUI.

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_tutor.py`:

```python
# ---------------------------------------------------------------------------
# cmd_tutor — CLI validation (no LLM, no TUI)
# ---------------------------------------------------------------------------

def test_tutor_cli_rejects_missing_file(tmp_path: Path) -> None:
    from locus_cli.main import main
    result = main(["tutor", str(tmp_path / "missing.py")])
    assert result != 0


def test_tutor_cli_rejects_binary_file(tmp_path: Path) -> None:
    from locus_cli.main import main
    binary = tmp_path / "img.png"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    result = main(["tutor", str(binary)])
    assert result != 0


def test_tutor_cli_rejects_oversized_file(tmp_path: Path) -> None:
    from locus_cli.main import main
    big = tmp_path / "big.py"
    big.write_text("\n".join(f"x = {i}" for i in range(501)))
    result = main(["tutor", str(big)])
    assert result != 0
```

- [ ] **Step 2: Run — verify they fail**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v -k "tutor_cli"
```

Expected: `SystemExit` or errors — `tutor` subcommand not registered yet.

- [ ] **Step 3: Add `cmd_tutor` and register subcommand in `main.py`**

Add `cmd_tutor` after `cmd_overview`:

```python
def cmd_tutor(args: argparse.Namespace) -> int:
    """ Handler for: `locus tutor` """
    from pathlib import Path
    from .core.tutor import TutorSession
    from .core.profiler import HardwareProfiler
    from .core.provisioner import Provisioner
    from .core.inference import check_gpu_support
    from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

    file_path = Path(args.file).expanduser().resolve()

    # Validate file before provisioning (fast fail)
    try:
        TutorSession(file_path, n_gpu_layers=0, _skip_workers=True)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    # Hardware profiling + tier selection
    profiler = HardwareProfiler()
    gpu_info = profiler.detect_gpu()
    ram_gb = profiler.get_total_ram_gb()
    provisioner = Provisioner()
    tier = provisioner.determine_tier(
        ram_gb=ram_gb,
        gpu_type=str(gpu_info.get("type", "CPU_ONLY")),
        vram_gb=float(gpu_info.get("vram_gb", 0.0)),
    )

    # Auto-select n_gpu_layers (no user prompt)
    n_gpu_layers = -1 if check_gpu_support() else 0

    # Model download advisory + download if needed
    # Approximate sizes (GB) per tier for the advisory message
    _MODEL_SIZES = {1: "4.7 GB", 2: "2.0 GB", 3: "1.0 GB", 4: "0.4 GB"}
    if not provisioner.is_model_cached(tier):
        model_name, _ = provisioner.MODELS[tier]
        model_size = _MODEL_SIZES.get(tier, "several GB")
        console.print(
            f"\n[bold]Model required:[/bold] {model_name}  (~{model_size})\n"
            f"[dim]Saved to: ~/.locus/models/{model_name}[/dim]\n"
            f"[yellow]This download may be slow depending on your connection speed.[/yellow]\n"
        )
        with Progress(
            "[dim]{task.description}[/dim]",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task(f"Downloading {model_name}", total=None)
            def _on_dl(downloaded: int, total: int) -> None:
                progress.update(task_id, completed=downloaded, total=total if total > 0 else None)
            provisioner.download_model(tier, on_progress=_on_dl)

    # Launch TUI
    from .ui.tutor_app import TutorApp
    app = TutorApp(
        file_path=file_path,
        model_path=provisioner.get_model_path(tier),
        n_gpu_layers=n_gpu_layers,
    )
    app.run()
    return 0
```

Register the subcommand inside `build_parser()`, after the `overview` block:

```python
    # ---- tutor command ----
    tutor_parser = subparser.add_parser("tutor", help="Line-by-line AI code tutor.")
    tutor_parser.add_argument("file", help="File to tutor.")
    tutor_parser.set_defaults(handler=cmd_tutor)
```

- [ ] **Step 4: Run — verify CLI tests pass**

```bash
source .venv/bin/activate && pytest tests/test_tutor.py -v -k "tutor_cli"
```

Expected: all 3 PASS (validation errors caught before TUI opens).

- [ ] **Step 5: Run full test suite — no regressions**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/locus_cli/main.py tests/test_tutor.py
git commit -m "feat: add cmd_tutor and locus tutor subcommand"
```

---

## Task 8: TutorApp — Layout

**Files:**
- Create: `src/locus_cli/ui/tutor_app.py`

No unit tests for Textual layout — verify manually by running `locus tutor` on a real file.

- [ ] **Step 1: Create `tutor_app.py` with side-by-side layout**

```python
"""
Textual TUI for `locus tutor`.

Side-by-side split: code viewer (left) + explanation panel (right).
Keyboard: j/k/↑/↓ navigate, Enter/Space reveal, q quit.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult, Message
from textual.containers import Horizontal
from textual.widgets import Footer, Static
from textual import work

from ..core.tutor import TutorSession


class SummaryReady(Message):
    """Posted by TutorSession.on_summary_ready callback → TutorApp."""


class TutorApp(App[None]):
    """Interactive line-by-line code tutor."""

    CSS = """
    TutorApp {
        background: $surface;
    }

    #split {
        height: 1fr;
    }

    #code-panel {
        width: 1fr;
        border-right: solid $primary-darken-2;
        overflow-y: auto;
        padding: 0 1;
    }

    #explanation-panel {
        width: 1fr;
        overflow-y: auto;
        padding: 1 2;
        color: $text;
    }

    .line-normal {
        color: $text-muted;
    }

    .line-highlight {
        background: $primary-darken-3;
        color: $text;
    }
    """

    BINDINGS = [
        ("j,down", "move_down", "Down"),
        ("k,up", "move_up", "Up"),
        ("enter,space", "reveal", "Reveal"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        file_path: Path,
        model_path: Path,
        n_gpu_layers: int,
    ) -> None:
        super().__init__()
        self._file_path = file_path
        self._model_path = model_path
        self._n_gpu_layers = n_gpu_layers
        self._cursor = 1  # 1-indexed
        self._session: TutorSession | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="split"):
            yield Static(id="code-panel", markup=False)
            yield Static(id="explanation-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._session = TutorSession(
            file_path=self._file_path,
            model_path=self._model_path,
            n_gpu_layers=self._n_gpu_layers,
            on_summary_ready=lambda: self.call_from_thread(
                self.post_message, SummaryReady()
            ),
        )
        self._render_code()
        self._set_explanation("Analyzing file...")

    # ------------------------------------------------------------------ #
    # Rendering helpers
    # ------------------------------------------------------------------ #

    def _render_code(self) -> None:
        """Re-render the code panel with the current line highlighted."""
        assert self._session is not None
        lines = self._session.lines
        parts: list[str] = []
        for i, line in enumerate(lines, start=1):
            num = f"{i:>4}  "
            text = line.rstrip("\n")
            if i == self._cursor:
                parts.append(f"[reverse]▶ {num}{text}[/reverse]")
            else:
                parts.append(f"[dim]  {num}[/dim]{text}")
        code_widget = self.query_one("#code-panel", Static)
        code_widget.update("\n".join(parts))

    def _set_explanation(self, text: str) -> None:
        self.query_one("#explanation-panel", Static).update(text)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def action_move_down(self) -> None:
        assert self._session is not None
        if self._cursor < len(self._session.lines):
            self._cursor += 1
            self._session.set_cursor(self._cursor)
            self._render_code()
            self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")

    def action_move_up(self) -> None:
        if self._cursor > 1:
            self._cursor -= 1
            if self._session:
                self._session.set_cursor(self._cursor)
            self._render_code()
            self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")

    def action_reveal(self) -> None:
        assert self._session is not None
        if not self._session._summary_ready.is_set():
            return  # still analyzing — reveal is disabled
        cached = self._session.get_explanation(self._cursor)
        if cached is not None:
            self._set_explanation(cached)
        else:
            self._set_explanation("[dim]Generating...[/dim]")
            self._fetch_explanation(self._cursor)

    def action_quit(self) -> None:
        self.exit()

    @work(thread=True)
    def _fetch_explanation(self, line_num: int) -> None:
        """Generate explanation on demand (runs in a thread)."""
        assert self._session is not None
        explanation = self._session.request_explanation(line_num)
        self.call_from_thread(self._set_explanation, explanation)

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #

    def on_summary_ready(self, _: SummaryReady) -> None:
        self._set_explanation(
            "Press [bold]Enter[/bold] or [bold]Space[/bold] to explain the current line."
        )
```

- [ ] **Step 2: Smoke-test the TUI manually**

> **Prerequisite:** The model must be cached before this test. If you have not run `locus overview` yet, run it once first so the model downloads. You can also confirm with:
> ```bash
> ls ~/.locus/models/
> ```
> If the directory is empty, run `locus overview .` and let it download before proceeding.

```bash
source .venv/bin/activate && locus tutor src/locus_cli/core/tutor.py
```

Verify:
- TUI opens with code in the left panel
- Right panel shows `Analyzing file...`, then transitions to the "Press Enter" prompt
- `j`/`k` and arrow keys move the highlighted line
- Pressing `Enter` on a line shows the explanation in the right panel
- `q` quits cleanly

- [ ] **Step 3: Commit**

```bash
git add src/locus_cli/ui/tutor_app.py
git commit -m "feat: add TutorApp Textual TUI with split layout and keyboard navigation"
```

---

## Task 9: Update PLAN.md and README

**Files:**
- Modify: `.agent/PLAN.md`
- Modify: `README.md`

- [ ] **Step 1: Mark `locus tutor` as implemented in PLAN.md**

In `.agent/PLAN.md`, under the roadmap section, change the `locus tutor` entry from a future item to a completed item. Update `## 2) Current State` to reflect the new command.

- [ ] **Step 2: Add `locus tutor` to the README commands table and roadmap**

In `README.md`:
- Add `locus tutor <file>` to the Commands section with a one-line description
- Mark `locus tutor` as `[x]` in the Roadmap

- [ ] **Step 3: Commit**

```bash
git add .agent/PLAN.md README.md
git commit -m "docs: mark locus tutor as implemented in PLAN.md and README"
```

---

## Task 10: Final Integration Check + PR

- [ ] **Step 1: Run full test suite**

```bash
source .venv/bin/activate && pytest -v
```

Expected: all tests PASS, no regressions.

- [ ] **Step 2: Type-check**

```bash
source .venv/bin/activate && mypy src/locus_cli
```

Fix any type errors before proceeding.

- [ ] **Step 3: End-to-end smoke test**

```bash
source .venv/bin/activate && locus tutor src/locus_cli/core/scanner.py
```

Navigate a few lines, press Enter to trigger an explanation (may require model download on first run), verify the right panel updates correctly.

- [ ] **Step 4: Push branch and open PR**

```bash
git push -u origin feature/tutor-command
```

Then open a PR from `feature/tutor-command` → `main` with a description of what was implemented.
