# Locus v0.1.0 Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix GPU detection/transparency, add streaming tutor explanations, sliding-window context, large-file support, shared SetupApp, thread safety, and release cleanup — making locus ready for PyPI v0.1.0.

**Architecture:** Extract `SetupApp` from `OverviewApp` so both `locus overview` and `locus tutor` share the same GPU/CPU selection screen. Refactor `TutorSession` to use sliding-window line prompts and streaming LLM output. All other fixes are self-contained changes to individual files.

**Tech Stack:** Python 3.10+, Textual (TUI), Rich (console), llama-cpp-python (local LLM), pytest, threading

---

## File Map

| File | Role after changes |
|---|---|
| `src/locus_cli/ui/setup_app.py` | **New.** Command-agnostic GPU/CPU selection screen. Replaces `overview_app.py`. |
| `src/locus_cli/ui/overview_app.py` | **Deleted.** |
| `src/locus_cli/core/inference.py` | Add `warn_if_gpu_unsupported`. Fix `n_ctx` 4096→8192. |
| `src/locus_cli/core/profiler.py` | Remove debug block. Add AMD VRAM via `rocm-smi`. |
| `src/locus_cli/core/provisioner.py` | Annotate unused `BINARIES` dict. |
| `src/locus_cli/core/tutor.py` | Sliding window, large-file sampling, `stream_explanation`, `_cache_lock`, limit raise. |
| `src/locus_cli/ui/tutor_app.py` | Streaming `_fetch_explanation`. Show cached explanations on navigation. |
| `src/locus_cli/main.py` | Wire `SetupApp` into both `cmd_overview` and `cmd_tutor`. |
| `README.md` | Add GPU Acceleration section. |
| `tests/test_tutor.py` | Delete 2 obsolete tests, update 1, add 3 new tests. |

---

## Task 1: Release Cleanup

**Files:**
- Modify: `src/locus_cli/core/profiler.py` (remove lines 86–94)
- Modify: `src/locus_cli/core/provisioner.py` (annotate BINARIES)

- [ ] **Step 1: Remove the `[REMOVE LATER]` debug block from profiler.py**

Delete the entire `if __name__ == "__main__":` block at the bottom (lines 86–94). The file should end after the closing `pass` of the AMD detection block.

- [ ] **Step 2: Annotate the BINARIES dict in provisioner.py**

Find the `BINARIES = {` line and insert a comment immediately above it:

```python
    # Reserved — not yet used. Planned for llama.cpp binary distribution in a future release.
    BINARIES = {
```

- [ ] **Step 3: Run all tests and verify they still pass**

```bash
uv run pytest --tb=short -q
```

Expected: `84 passed`

- [ ] **Step 4: Commit**

```bash
git add src/locus_cli/core/profiler.py src/locus_cli/core/provisioner.py
git commit -m "chore: release cleanup — remove debug block, annotate unused BINARIES"
```

---

## Task 2: inference.py — n_ctx Fix + warn_if_gpu_unsupported

**Files:**
- Modify: `src/locus_cli/core/inference.py`

- [ ] **Step 1: Update `n_ctx` in `stream_overview`**

In `inference.py`, find the `Llama(` call inside `stream_overview` and change `n_ctx=4096` to `n_ctx=8192`.

- [ ] **Step 2: Add `warn_if_gpu_unsupported` function**

Add this function to `inference.py` after `gpu_install_hint`:

```python
def warn_if_gpu_unsupported(gpu_type: str, n_gpu_layers: int) -> None:
    """Print a warning to console if GPU was requested but is not supported."""
    if n_gpu_layers != -1:
        return
    if check_gpu_support():
        return
    from ..ui.console import console
    hint_nvidia = _GPU_INSTALL_HINTS.get("NVIDIA", "")
    hint_amd = _GPU_INSTALL_HINTS.get("AMD", "")
    console.print(
        "\n[yellow]Warning: llama-cpp-python was not compiled with GPU support.\n"
        "Inference will run on CPU. To enable GPU acceleration:\n\n"
        f"  NVIDIA: {hint_nvidia}\n"
        f"  AMD:    {hint_amd}[/yellow]\n"
    )
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest --tb=short -q
```

Expected: `84 passed`

- [ ] **Step 4: Commit**

```bash
git add src/locus_cli/core/inference.py
git commit -m "feat: fix n_ctx 4096→8192, add warn_if_gpu_unsupported helper"
```

---

## Task 3: Create setup_app.py (SetupApp replaces OverviewApp)

**Files:**
- Create: `src/locus_cli/ui/setup_app.py`
- Delete: `src/locus_cli/ui/overview_app.py`

- [ ] **Step 1: Create `setup_app.py` as a copy of `overview_app.py` with the following changes**

Create `src/locus_cli/ui/setup_app.py` with this exact content:

```python
"""
Textual TUI for GPU/CPU setup screen — shared by `locus overview` and `locus tutor`.

Shows detected hardware and asks the user whether to run on GPU or CPU.
Returns n_gpu_layers (-1 = full GPU offload, 0 = CPU) via app.run().

After the app exits, the caller handles model download and inference.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from ..core.provisioner import Provisioner


class SetupApp(App[int]):
    """Setup screen: display hardware info and collect GPU/CPU preference."""

    CSS = """
    SetupApp {
        background: $surface;
        align: center middle;
    }

    #panel {
        border: round $primary;
        padding: 1 3;
        width: 64;
        height: auto;
    }

    #hardware {
        height: auto;
        margin-bottom: 1;
    }

    #note {
        color: $warning;
        height: auto;
        margin-bottom: 1;
    }

    #status {
        color: $text-muted;
        height: auto;
    }

    #controls {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        title: str,
        tier: int,
        provisioner: Provisioner,
        gpu_info: dict,
    ) -> None:
        super().__init__()
        self._title = title
        self.tier = tier
        self.provisioner = provisioner
        self.gpu_info = gpu_info
        gpu_type: str = str(gpu_info.get("type", "CPU_ONLY"))
        self._has_gpu = gpu_type not in ("CPU_ONLY", "")
        self._gpu_type = gpu_type
        self._gpu_supported = self._detect_gpu_support()

    @staticmethod
    def _detect_gpu_support() -> bool:
        from ..core.inference import check_gpu_support
        return check_gpu_support()

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static(id="hardware")
            yield Static(id="note")
            yield Static(id="status")
            with Horizontal(id="controls"):
                yield Button("GPU  [G]", id="btn-gpu", variant="success")
                yield Button("CPU  [C]", id="btn-cpu", variant="default")

    def on_mount(self) -> None:
        # Set panel border title
        self.query_one("#panel", Vertical).border_title = self._title

        vram: float = float(self.gpu_info.get("vram_gb", 0.0))
        model_name, _ = self.provisioner.MODELS[self.tier]
        cached = self.provisioner.is_model_cached(self.tier)

        # Hardware line
        if self._gpu_type == "APPLE_SILICON":
            gpu_line = f"  GPU    Apple Silicon  ({vram:.0f} GB unified)"
        elif self._has_gpu:
            vram_str = f"  ·  {vram:.1f} GB VRAM" if vram > 0 else ""
            gpu_line = f"  GPU    {self._gpu_type}{vram_str}"
        else:
            gpu_line = "  GPU    Not detected"

        cache_tag = "  [dim](cached)[/dim]" if cached else ""
        self.query_one("#hardware", Static).update(
            f"[bold]Hardware[/bold]\n{gpu_line}\n\n"
            f"[bold]Model[/bold]   {model_name}  (Tier {self.tier}){cache_tag}"
        )

        note = self.query_one("#note", Static)
        status = self.query_one("#status", Static)
        controls = self.query_one("#controls", Horizontal)

        if not self._has_gpu:
            note.display = False
            controls.display = False
            status.update(
                "[dim]No GPU detected — running on CPU.\n"
                "Press [bold]Enter[/bold] to continue.[/dim]"
            )
        elif not self._gpu_supported:
            from ..core.inference import gpu_install_hint
            hint = gpu_install_hint(self._gpu_type) or ""
            note.update(
                f"[yellow]llama-cpp-python may not have GPU support compiled in.\n"
                f"To enable it:  {hint}[/yellow]"
            )
            status.update("[dim]Choose how to run inference:[/dim]")
        else:
            note.display = False
            status.update("[dim]Choose how to run inference:[/dim]")

    # ------------------------------------------------------------------ #
    # Input
    # ------------------------------------------------------------------ #

    def on_key(self, event) -> None:
        key = event.key
        if key == "h" and self._has_gpu:
            self.query_one("#btn-gpu", Button).focus()
        elif key == "l" and self._has_gpu:
            self.query_one("#btn-cpu", Button).focus()
        elif key == "g" and self._has_gpu:
            self.exit(-1)
        elif key == "c":
            self.exit(0)
        elif key == "enter" and not self._has_gpu:
            self.exit(0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-gpu" and self._has_gpu:
            self.exit(-1)
        elif event.button.id == "btn-cpu":
            self.exit(0)
```

- [ ] **Step 2: Delete `overview_app.py`**

```bash
rm src/locus_cli/ui/overview_app.py
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest --tb=short -q
```

Expected: `84 passed` (no test imports `OverviewApp` directly)

- [ ] **Step 4: Commit**

```bash
# git add on the deleted file stages the deletion — this is correct and intentional
git add src/locus_cli/ui/setup_app.py src/locus_cli/ui/overview_app.py
git commit -m "feat: extract SetupApp from OverviewApp — shared GPU/CPU screen"
```

---

## Task 4: Update main.py — Wire SetupApp into Both Commands

**Files:**
- Modify: `src/locus_cli/main.py`

- [ ] **Step 1: Update `cmd_overview` to import `SetupApp` and call `warn_if_gpu_unsupported`**

In `cmd_overview`, find the import of `OverviewApp` and the `app = OverviewApp(...)` line. Replace them:

Old:
```python
    from .ui.overview_app import OverviewApp
    ...
    app = OverviewApp(tier=tier, provisioner=provisioner, gpu_info=gpu_info)
    n_gpu_layers: int = app.run() or 0
```

New:
```python
    from .ui.setup_app import SetupApp
    from .core.inference import stream_overview, warn_if_gpu_unsupported
    ...
    app = SetupApp(title="Overview", tier=tier, provisioner=provisioner, gpu_info=gpu_info)
    n_gpu_layers: int = app.run() or 0
    warn_if_gpu_unsupported(str(gpu_info.get("type", "CPU_ONLY")), n_gpu_layers)
```

Note: also remove the separate `from .core.inference import stream_overview` import if it was standalone — consolidate into the one line above.

- [ ] **Step 2: Rewrite `cmd_tutor` GPU selection block**

In `cmd_tutor`, find and **replace** this block:

```python
    # Auto-select n_gpu_layers (no user prompt)
    with console.status("[dim]Initializing AI backend...[/dim]", spinner="dots"):
        n_gpu_layers = -1 if check_gpu_support() else 0
```

With:

```python
    # GPU/CPU selection screen
    from .ui.setup_app import SetupApp
    from .core.inference import warn_if_gpu_unsupported
    app = SetupApp(title="Tutor", tier=tier, provisioner=provisioner, gpu_info=gpu_info)
    n_gpu_layers: int = app.run() or 0
    warn_if_gpu_unsupported(str(gpu_info.get("type", "CPU_ONLY")), n_gpu_layers)
```

Also remove the now-unused `from .core.inference import check_gpu_support` import in `cmd_tutor`.

- [ ] **Step 3: Run tests**

```bash
uv run pytest --tb=short -q
```

Expected: `84 passed`

- [ ] **Step 4: Commit**

```bash
git add src/locus_cli/main.py
git commit -m "feat: add SetupApp + GPU warning to cmd_tutor, update cmd_overview import"
```

---

## Task 5: AMD VRAM Detection in profiler.py

**Files:**
- Modify: `src/locus_cli/core/profiler.py`

- [ ] **Step 1: Add `rocm-smi` VRAM detection for AMD**

In `profiler.py`, find the AMD detection block (currently `if gpu_info["type"] == "CPU_ONLY": ...`). After detecting AMD via `lspci` or `wmic` and setting `gpu_info = {"type": "AMD", "vram_gb": 0.0}`, add VRAM detection before the `pass`. Replace the AMD detection block with:

```python
        # 3. AMD Check
        if gpu_info["type"] == "CPU_ONLY":
            try:
                if system == "Windows":
                    result = subprocess.run(
                        ["wmic", "path", "win32_VideoController", "get", "name"],
                        capture_output=True, text=True
                    )
                    if "AMD" in result.stdout.upper() or "RADEON" in result.stdout.upper():
                        gpu_info = {"type": "AMD", "vram_gb": 0.0}

                elif system == "Linux":
                    result = subprocess.run(
                        ["lspci"],
                        capture_output=True, text=True
                    )
                    if "AMD" in result.stdout.upper() or "RADEON" in result.stdout.upper():
                        gpu_info = {"type": "AMD", "vram_gb": 0.0}

            except FileNotFoundError:
                pass

        # 4. AMD VRAM via rocm-smi (Linux only, best-effort)
        if gpu_info["type"] == "AMD":
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showmeminfo", "vram", "--noheader"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if "VRAM Total Memory (B):" in line:
                            vram_bytes = int(line.split(":")[-1].strip())
                            gpu_info["vram_gb"] = round(vram_bytes / 1024**3, 2)
                            break
            except Exception:
                pass  # rocm-smi not available or parse failed — keep 0.0
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest --tb=short -q
```

Expected: `84 passed`

- [ ] **Step 3: Commit**

```bash
git add src/locus_cli/core/profiler.py
git commit -m "feat: detect AMD VRAM via rocm-smi"
```

---

## Task 6: tutor.py — File Limits, Sliding Window, Large-File Sampling (TDD)

**Files:**
- Modify: `tests/test_tutor.py`
- Modify: `src/locus_cli/core/tutor.py`

- [ ] **Step 1: Delete obsolete tests in test_tutor.py**

Remove the following two test functions entirely from `tests/test_tutor.py`:
- `test_tutor_session_raises_when_file_too_long` (tests old 500-line limit)
- `test_tutor_cli_rejects_oversized_file` (tests old 501-line CLI rejection)

- [ ] **Step 2: Update the byte-limit test**

Find `test_tutor_session_raises_when_file_too_large` and replace its body:

```python
def test_tutor_session_raises_when_file_too_large(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    big = tmp_path / "big.py"
    # Write just over 500 KB
    big.write_bytes(b"x" * (500 * 1024 + 1))
    with pytest.raises(ValueError, match="500 KB"):
        TutorSession(big, n_gpu_layers=0)
```

- [ ] **Step 3: Add the sliding window test**

Append to `tests/test_tutor.py`:

```python
def test_build_line_prompt_sliding_window(tmp_path: Path) -> None:
    """Prompt should contain only a window of lines, not the full file."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "big.py"
    # 200-line file: line N contains "LINE_N"
    src.write_text("\n".join(f"# LINE_{i}" for i in range(1, 201)))
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"

    prompt = session.build_line_prompt(line_num=100)

    # Should contain the window header
    assert "Lines 60" in prompt
    assert "140 of 200" in prompt
    # Should contain lines within the window
    assert "LINE_60" in prompt
    assert "LINE_140" in prompt
    # Should NOT contain lines outside the window
    assert "LINE_1" not in prompt
    assert "LINE_200" not in prompt
```

- [ ] **Step 4: Add the large-file summary sampling test**

```python
def test_build_summary_prompt_large_file_uses_sampling(tmp_path: Path) -> None:
    """Summary prompt for large files should use head+middle+tail sampling."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "large.py"
    # 500-line file: each line is "# LINE_N"
    src.write_text("\n".join(f"# LINE_{i}" for i in range(1, 501)))
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)

    prompt = session.build_summary_prompt()

    # Should contain the omission marker
    assert "[..." in prompt
    # Should contain head lines
    assert "LINE_1" in prompt
    assert "LINE_300" in prompt
    # Should contain tail lines
    assert "LINE_500" in prompt
    # Should NOT contain all 500 lines verbatim
    assert prompt.count("LINE_") < 500
```

- [ ] **Step 5: Run the new tests to verify they fail**

```bash
uv run pytest tests/test_tutor.py::test_build_line_prompt_sliding_window tests/test_tutor.py::test_build_summary_prompt_large_file_uses_sampling tests/test_tutor.py::test_tutor_session_raises_when_file_too_large -v
```

Expected: all 3 FAIL (old byte limit message says "20 KB", sliding window not implemented yet)

- [ ] **Step 6: Update `_MAX_BYTES` and remove `_MAX_LINES` in tutor.py**

At the top of `tutor.py`:
- Change `_MAX_BYTES = 20 * 1024` → `_MAX_BYTES = 500 * 1024`
- Delete the `_MAX_LINES = 500` line entirely

In `_load_and_validate`, delete the lines-too-long check:
```python
# DELETE THIS BLOCK:
if len(lines) > _MAX_LINES:
    raise ValueError(
        f"File too long: {len(lines)} lines (max {_MAX_LINES}). "
        "Large-file tutoring is not supported in v0.1.0."
    )
```

Update the bytes error message:
```python
if len(raw) > _MAX_BYTES:
    raise ValueError(
        f"File too large: {len(raw) / 1024:.0f} KB (max 500 KB)."
    )
```

- [ ] **Step 7: Rewrite `build_line_prompt` with sliding window**

Replace the entire `build_line_prompt` method with the following. Note: `_WINDOW` is a **class attribute** (same pattern as the existing `_PREFETCH_AHEAD = 20` class attribute) — place it inside the `TutorSession` class body alongside `_PREFETCH_AHEAD`, not at module level:

```python
    _WINDOW = 40  # lines of context on each side of the cursor

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
```

- [ ] **Step 8: Rewrite `build_summary_prompt` with large-file sampling**

Replace the entire `build_summary_prompt` method with the following. Note: `_SUMMARY_SAMPLE_THRESHOLD` is also a **class attribute** — place it in the class body alongside `_WINDOW` and `_PREFETCH_AHEAD`:

```python
    _SUMMARY_SAMPLE_THRESHOLD = 400

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

        if mid_start < mid_end:
            omitted_before = mid_start - 300
            sections.append(f"[... {omitted_before} lines omitted ...]")
            sections.append("\n".join(self.lines[mid_start:mid_end]))

        omitted_before_tail = total - 100 - (mid_end if mid_start < mid_end else 300)
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
```

- [ ] **Step 9: Run all tests**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass (82 tests — 2 deleted, 1 updated, 3 new = net +1 → was 84, now 83)

- [ ] **Step 10: Commit**

```bash
git add tests/test_tutor.py src/locus_cli/core/tutor.py
git commit -m "feat: raise file limit to 500KB, sliding window context, large-file summary sampling"
```

---

## Task 7: tutor.py — stream_explanation + Thread Safety (TDD)

**Files:**
- Modify: `tests/test_tutor.py`
- Modify: `src/locus_cli/core/tutor.py`

- [ ] **Step 1: Write the failing test for `stream_explanation`**

Append to `tests/test_tutor.py`:

```python
def test_stream_explanation_fires_tokens_and_done(tmp_path: Path) -> None:
    """stream_explanation calls on_token for each token and on_done with full text."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"

    tokens_received: list[str] = []
    done_text: list[str] = []

    def fake_stream(prompt: str, on_token_fn: object) -> str:
        for tok in ["Hello", " ", "world"]:
            on_token_fn(tok)  # type: ignore[operator]
        return "Hello world"

    session.stream_explanation(
        line_num=1,
        on_token=tokens_received.append,
        on_done=done_text.append,
        _stream_fn=fake_stream,
    )

    assert tokens_received == ["Hello", " ", "world"]
    assert done_text == ["Hello world"]
    assert session.get_explanation(1) == "Hello world"


def test_stream_explanation_caches_result(tmp_path: Path) -> None:
    """stream_explanation stores result in line_cache via on_done."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"

    session.stream_explanation(
        line_num=1,
        on_token=lambda t: None,
        on_done=lambda full: None,
        _stream_fn=lambda p, cb: (cb("ok"), "ok")[1],
    )

    assert session.get_explanation(1) == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tutor.py::test_stream_explanation_fires_tokens_and_done tests/test_tutor.py::test_stream_explanation_caches_result -v
```

Expected: FAIL with `AttributeError: 'TutorSession' object has no attribute 'stream_explanation'`

- [ ] **Step 3: Add `_cache_lock` to `TutorSession.__init__`**

In `tutor.py`, inside `__init__` after `self._llm_lock = threading.Lock()`, add:

```python
        self._cache_lock = threading.Lock()
```

- [ ] **Step 4: Add `stream_explanation` method to `TutorSession`**

Add after `_call_llm`:

```python
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
```

- [ ] **Step 5: Add `_cache_lock` guards to `_run_worker_b` and `request_explanation`**

In `_run_worker_b`, find:
```python
                self.line_cache[line_num] = explanation
```
Wrap it:
```python
                with self._cache_lock:
                    self.line_cache[line_num] = explanation
```

In `request_explanation`, find:
```python
        self.line_cache[line_num] = explanation
```
Wrap it:
```python
        with self._cache_lock:
            self.line_cache[line_num] = explanation
```

- [ ] **Step 6: Run all tests**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add src/locus_cli/core/tutor.py tests/test_tutor.py
git commit -m "feat: add stream_explanation, _cache_lock thread safety to TutorSession"
```

---

## Task 8: tutor_app.py — Streaming + Cached Navigation

**Files:**
- Modify: `src/locus_cli/ui/tutor_app.py`

- [ ] **Step 1: Rework `_fetch_explanation` to use streaming**

Replace the existing `_fetch_explanation` method entirely:

```python
    @work(thread=True)
    def _fetch_explanation(self, line_num: int) -> None:
        assert self._session is not None
        first_token = True
        accumulated: list[str] = []  # str accumulator — avoids reading panel.renderable

        def _on_token(token: str) -> None:
            nonlocal first_token
            accumulated.append(token)
            current_text = "".join(accumulated)

            def _update() -> None:
                nonlocal first_token
                if first_token:
                    self._stop_loading_animation()
                    first_token = False
                self._set_explanation(current_text)

            self.call_from_thread(_update)

        def _on_done(full_text: str) -> None:
            # line_cache already written by stream_explanation in this thread.
            # Final render with authoritative full_text corrects any partial-update artefacts.
            self.call_from_thread(self._set_explanation, full_text)

        self._session.stream_explanation(line_num, _on_token, _on_done)
```

- [ ] **Step 2: Show cached explanations immediately on navigation**

In `action_move_down`, replace the current `_set_explanation(...)` call at the end:

Old:
```python
            self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")
```

New:
```python
            cached = self._session.get_explanation(self._cursor)
            if cached is not None:
                self._stop_loading_animation()
                self._set_explanation(cached)
            else:
                self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")
```

Apply the same change to `action_move_up`.

- [ ] **Step 3: Run all tests**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add src/locus_cli/ui/tutor_app.py
git commit -m "feat: streaming tutor explanations, show cached explanation on navigation"
```

---

## Task 9: README — GPU Acceleration Section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current README to find the installation section**

Open `README.md` and locate the installation section (look for `pip install` or `## Installation`).

- [ ] **Step 2: Insert the GPU Acceleration section immediately after the installation section**

Add this block after the installation section:

````markdown
## GPU Acceleration

The default installation uses a CPU-only build of `llama-cpp-python`. To enable GPU acceleration, reinstall it with the appropriate backend:

**NVIDIA (CUDA 12.1):**
```bash
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

**AMD (ROCm 6.0):**
```bash
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/rocm60
```

**Apple Silicon:** GPU acceleration via Metal is enabled automatically with the default install — no extra steps needed.

> Locus will display a warning at runtime if GPU was selected but is not available, along with the exact install command for your platform.
````

- [ ] **Step 3: Run tests one final time**

```bash
uv run pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: add GPU Acceleration section to README"
```

---

## Final Verification

- [ ] **Run the full test suite**

```bash
uv run pytest -v
```

All tests should pass. Count should be 83+ (was 84, deleted 2, added 3).

- [ ] **Check mypy on changed files**

```bash
uv run mypy src/locus_cli/core/tutor.py src/locus_cli/core/inference.py src/locus_cli/ui/setup_app.py src/locus_cli/ui/tutor_app.py src/locus_cli/main.py
```

Expected: no errors.
