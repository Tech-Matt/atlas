# Locus v0.1.0 Improvements — Design Spec

**Date:** 2026-03-24
**Scope:** GPU fix, performance, UX, release cleanup

---

## 1. Problem Statement

Several issues block a clean v0.1.0 PyPI release:

- `locus tutor` silently runs on CPU even on GPU-capable machines (no setup screen, no warning)
- `locus overview` lets the user select GPU but silently falls back to CPU when `llama-cpp-python` lacks GPU support — no actionable guidance given
- `locus tutor` explanations are blocking (full response wait); no streaming
- `build_line_prompt` sends the full file on every line request — slow and wasteful
- File size cap (500 lines / 20KB) is too small for the intended use case (Linux kernel source)
- Cached explanations are not shown on navigation — always prompts "Press Enter..."
- `line_cache` has a write-write race condition between Worker B and `_fetch_explanation`
- Dead code and debug artifacts not suitable for PyPI (`BINARIES` dict, `[REMOVE LATER]` block)
- README has no GPU acceleration guidance

---

## 2. Approach

**Approach B — Shared setup screen + focused refactors.**

Extract a command-agnostic `SetupApp` from `OverviewApp`, fix each remaining issue as a self-contained change. No deep architectural overhaul.

---

## 3. Design

### 3.1 Shared GPU/CPU Setup Screen

**File:** `src/locus_cli/ui/setup_app.py` (new, replaces `overview_app.py`)

`OverviewApp` is renamed to `SetupApp`. It becomes command-agnostic:

```python
class SetupApp(App[int]):
    def __init__(self, title: str, tier: int, provisioner: Provisioner, gpu_info: dict) -> None:
```

- `title` is displayed as the panel border label using Textual's `border_title` property on the `#panel` Vertical widget, set in `on_mount`. Example: `self.query_one("#panel").border_title = self._title`.
- The CSS class selector is updated from `OverviewApp { ... }` to `SetupApp { ... }`.
- Returns `int`: `-1` for GPU, `0` for CPU — unchanged.
- All GPU detection logic, warning display, and button behaviour remain identical.

`overview_app.py` is deleted. Both `cmd_overview` and `cmd_tutor` import `SetupApp` from `ui/setup_app.py`. No existing test imports `OverviewApp` directly — confirmed by grep.

**`cmd_tutor` control flow with SetupApp** (replaces current auto-detect logic):

```
1. Validate file (fast fail, _skip_workers=True) — unchanged
2. Hardware profiling: detect GPU, RAM, determine tier — unchanged
3. Launch SetupApp(title="Tutor", tier=tier, provisioner=provisioner, gpu_info=gpu_info)
   → user picks GPU or CPU → returns n_gpu_layers (-1 or 0)
4. Call warn_if_gpu_unsupported(gpu_type, n_gpu_layers) — print warning if needed
5. Download model if not cached — unchanged
6. Launch TutorApp with n_gpu_layers — unchanged
```

The existing `with console.status("[dim]Initializing AI backend...[/dim]")` block and the `check_gpu_support()` auto-detect line are removed. The user now always chooses explicitly.

**GPU warning (post-TUI):** A shared helper `warn_if_gpu_unsupported(gpu_type: str, n_gpu_layers: int) -> None` lives in **`core/inference.py`** (alongside `check_gpu_support` and `gpu_install_hint` which it depends on). It prints to the shared `console` instance if `n_gpu_layers == -1` and `check_gpu_support()` returns `False`:

```
[yellow]Warning: llama-cpp-python was not compiled with GPU support.
Inference will run on CPU. To enable GPU acceleration:

  NVIDIA: pip install llama-cpp-python \
            --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
  AMD:    pip install llama-cpp-python \
            --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/rocm60
[/yellow]
```

Called from both `cmd_overview` and `cmd_tutor` immediately after `SetupApp.run()` returns.

---

### 3.2 Streaming Tutor Explanations

**File:** `src/locus_cli/core/tutor.py`

Add `stream_explanation` to `TutorSession`:

```python
def stream_explanation(
    self,
    line_num: int,
    on_token: Callable[[str], None],
    on_done: Callable[[str], None],
    _stream_fn: Callable[[str, Callable[[str], None]], str] | None = None,
) -> None:
```

- `_stream_fn` is injectable for tests (same pattern as existing `_llm_fn` on `request_explanation`). In production it is `None` and the real LLM is used.
- When `_stream_fn` is `None`, acquires `_llm_lock`, calls `llm.create_chat_completion(stream=True)`, fires `on_token(token)` for each non-empty token delta, accumulates `full_text`, then fires `on_done(full_text)` after the loop and after releasing the lock.
- `on_done` stores `full_text` in `line_cache` **inside the streaming thread** (not via `call_from_thread`), protected by `_cache_lock` (see §3.5).
- `on_token` and `on_done` must be safe to call from a background thread — callers are responsible for routing to the main thread if needed (see TutorApp below).

`_call_llm` is kept unchanged and used exclusively by **Worker B** (prefetch). Streaming is only triggered by explicit user input.

**Worker B interruption policy:** When the user presses Enter and `stream_explanation` is called, it blocks on `_llm_lock` until the current Worker B inference call finishes. This means the user may wait up to one inference cycle (~2–10s depending on hardware) before streaming starts. The loading animation continues during this wait — no additional UI state is needed. Worker B is **not** interrupted; this avoids complexity and the wait is bounded.

**File:** `src/locus_cli/ui/tutor_app.py`

`_fetch_explanation` is reworked. The `@work(thread=True)` decorator is **kept** — it provides Textual's worker lifecycle management and exception isolation. The body changes to call `stream_explanation` with thread-safe callbacks:

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

The `accumulated` list is local to the `@work` thread — only `_on_token` writes to it, so no locking is needed. `_set_explanation` replaces the panel content on each token (not appends), which is safe and avoids any type issues with `Static.renderable`.

---

### 3.3 Sliding Window Context + File Size Limits

**File:** `src/locus_cli/core/tutor.py`

**`build_line_prompt` — sliding window:**

- `WINDOW = 40` (±40 lines), giving up to 81 lines of context
- `start = max(1, line_num - WINDOW)`
- `end = min(len(self.lines), line_num + WINDOW)`
- Window lines are joined with newlines
- If `file_summary` is `None` (Worker A not yet complete), substitute `"(summary not yet available)"` as a fallback. In practice this only occurs if `request_explanation` is called directly before Worker A finishes — the TutorApp guards against this, but the method must be safe regardless.

Prompt structure:

```
You are a code tutor helping a developer understand a file line by line.

FILE SUMMARY:
{file_summary or "(summary not yet available)"}

EXCERPT (Lines {start}–{end} of {total}):
---
{window_lines}
---

The developer is currently on line {line_num}:
>>> {line_content}

Explain this line in plain language. If the line is part of a larger logical block
(a function, class, loop, condition), also explain its role in that context.
Be concise — 2-5 sentences.
```

**`build_summary_prompt` — large-file sampling:**

Threshold: `_SUMMARY_SAMPLE_THRESHOLD = 400` lines.

- If `len(self.lines) <= _SUMMARY_SAMPLE_THRESHOLD`: send full content (unchanged).
- If `len(self.lines) > _SUMMARY_SAMPLE_THRESHOLD`: build a sample with three slices:
  - **Head:** lines `[0:300]` (first 300 lines, 0-indexed)
  - **Middle:** 100 lines centred on the file midpoint. `mid = len(self.lines) // 2`. `mid_start = max(300, mid - 50)`. `mid_end = min(len(self.lines) - 100, mid_start + 100)`. If `mid_start >= mid_end` (file too short for a non-overlapping middle slice), skip the middle block entirely and only use head + tail.
  - **Tail:** last 100 lines: `lines[-100:]`
  - Sections separated by `\n[... {N} lines omitted ...]\n` where N is the actual number of omitted lines.

**File size limits:**

- Remove the 500-line hard limit entirely (`_MAX_LINES` constant and the `len(lines) > _MAX_LINES` check are deleted).
- Raise byte limit: `_MAX_BYTES = 500 * 1024` (500 KB).
- Error message updated: `f"File too large: {len(raw) / 1024:.0f} KB (max 500 KB)."`.
- Binary detection unchanged (null-byte check on latin-1 decode).

**Test updates required:**

- `test_tutor_session_raises_when_file_too_long`: **delete** — the line limit no longer exists.
- `test_tutor_cli_rejects_oversized_file`: **delete** — it tests the old 501-line rejection; after the line limit is removed, a 501-line file within 500 KB is accepted and `main()` returns 0, causing the test to fail.
- `test_tutor_session_raises_when_file_too_large`: update to write `b"x" * (500 * 1024 + 1)` (501 KB of data), assert `ValueError` matching `"500 KB"`.
- Add `test_build_line_prompt_sliding_window`: create a session with a 200-line file (`_skip_workers=True`), call `build_line_prompt(100)`, assert prompt contains `Lines 60–140 of 200` and does not contain the text of lines 1 or 200.
- Add `test_build_summary_prompt_large_file`: create a session with a 500-line file (`_skip_workers=True`), call `build_summary_prompt()`, assert it contains `[... ` and does not contain all 500 lines verbatim.

---

### 3.4 UI — Show Cached Explanations on Navigation

**File:** `src/locus_cli/ui/tutor_app.py`

In `action_move_down` and `action_move_up`: after updating `_cursor` and calling `_render_code`, check the cache:

```python
cached = self._session.get_explanation(self._cursor)
if cached is not None:
    self._stop_loading_animation()
    self._set_explanation(cached)
else:
    self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")
```

This replaces the current unconditional `_set_explanation("Press [bold]Enter[/bold]...")` call.

---

### 3.5 Thread Safety for `line_cache`

**File:** `src/locus_cli/core/tutor.py`

Add `self._cache_lock = threading.Lock()` to `TutorSession.__init__`.

Writes to `line_cache`:
- In `_run_worker_b`: the existing `if line_num not in self.line_cache:` check-then-write sequence is kept **outside** the lock for the read, but the write is protected: `with self._cache_lock: self.line_cache[line_num] = explanation`. A TOCTOU double-write is possible (two threads both see a miss and both write), but is harmless — both calls use identical prompts and would produce semantically equivalent results. The second write simply overwrites with an equivalent value.
- In `stream_explanation` (inside streaming thread, before `on_done` fires): `with self._cache_lock: self.line_cache[line_num] = full_text`
- In `request_explanation` (legacy synchronous path, still used by tests): `with self._cache_lock: self.line_cache[line_num] = explanation`

Reads in `get_explanation` and the cache-check at the top of `request_explanation` are plain dict reads and do not acquire the lock (GIL-safe for dict lookups in CPython).

**Worker B blocking during streaming:** `_llm_lock` is held for the entire duration of `stream_explanation` (which can be 30–120 seconds). This means once streaming starts, Worker B cannot make forward progress until streaming completes. This is an intentional and acceptable trade-off: the user is actively reading the streamed explanation, so prefetch is not urgent. Worker B resumes automatically once streaming finishes and the lock is released.

---

### 3.6 Consistency Fixes

**`n_ctx`:** `stream_overview` in `inference.py` is updated from `n_ctx=4096` to `n_ctx=8192`. Trade-off: this doubles peak RAM usage for the model's KV cache (~200–400 MB extra depending on model tier). On Tier 3 and 4 machines (8 GB RAM), this is still well within bounds. The benefit is that large codebase context (long READMEs, deep tree summaries) no longer gets truncated.

**AMD VRAM detection (`profiler.py`):** Before falling back to `0.0`, attempt:

```python
result = subprocess.run(
    ["rocm-smi", "--showmeminfo", "vram", "--noheader"],
    capture_output=True, text=True
)
```

Expected output format per GPU:
```
GPU[0]		: VRAM Total Memory (B): 8589934592
GPU[0]		: VRAM Total Used Memory (B): 123456789
```

Parse: find the first line containing `"VRAM Total Memory (B):"`, split on `":"`, take the last element, strip, convert to `int`, divide by `1024**3`, round to 2 decimal places. Wrap in `try/except Exception` and fall back to `0.0` on any failure (tool not found, parse error, etc.).

---

### 3.7 Release Cleanup

- **`profiler.py`:** Remove the `if __name__ == "__main__":` block (lines 86–94) entirely.
- **`provisioner.py`:** Prepend the `BINARIES` dict with the comment:
  ```python
  # Reserved — not yet used. Planned for llama.cpp binary distribution in a future release.
  ```
- **`overview_app.py`:** File deleted. No existing test file imports `OverviewApp` directly.

---

### 3.8 README — GPU Acceleration Section

Add a **"GPU Acceleration"** section immediately after the installation section:

```markdown
## GPU Acceleration

The default installation uses a CPU-only build of `llama-cpp-python`. To enable GPU acceleration:

**NVIDIA (CUDA 12.1):**
```
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

**AMD (ROCm 6.0):**
```
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/rocm60
```

**Apple Silicon:** GPU acceleration (Metal) is enabled automatically with the default install.

Locus will display a warning at runtime if GPU was selected but is not available, with the exact install command for your platform.
```

---

## 4. Files Changed

| File | Change |
|---|---|
| `src/locus_cli/ui/setup_app.py` | New — replaces `overview_app.py` |
| `src/locus_cli/ui/overview_app.py` | Deleted |
| `src/locus_cli/core/tutor.py` | Sliding window, large-file sampling, streaming, thread safety, limit raise |
| `src/locus_cli/core/inference.py` | `n_ctx` 4096→8192, `warn_if_gpu_unsupported` helper added |
| `src/locus_cli/core/profiler.py` | Remove debug block, AMD VRAM detection via `rocm-smi` |
| `src/locus_cli/core/provisioner.py` | Annotate `BINARIES` dict |
| `src/locus_cli/ui/tutor_app.py` | Streaming worker, cached explanation on navigation, import `SetupApp` |
| `src/locus_cli/main.py` | `cmd_tutor`: SetupApp + `warn_if_gpu_unsupported`; `cmd_overview`: same |
| `README.md` | GPU Acceleration section |
| `tests/test_tutor.py` | Delete line-limit tests, update byte-limit test, add sliding window + sampling tests |

---

## 5. Out of Scope (future)

- Chunk-based multi-section summaries for extremely large files (> 5000 lines)
- `--gpu` / `--cpu` CLI flags to bypass the setup screen
- Binary distribution via `BINARIES` matrix
- AMD VRAM detection via Vulkan
