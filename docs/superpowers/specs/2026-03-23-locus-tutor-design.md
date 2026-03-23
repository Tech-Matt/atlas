# locus tutor — Design Spec

**Date:** 2026-03-23
**Status:** Approved

---

## Overview

`locus tutor <file>` is an interactive, line-by-line code tutoring command for `locus`. The user navigates through a file one line at a time in a Textual TUI. On demand, the tutor generates a plain-language explanation of the current line — aware of the full file context — and displays it in a side panel. Explanations are pre-generated in the background so the experience feels instant.

**Primary use case:** Re-understanding code you've lost track of (AI-generated, inherited, or simply forgotten), or onboarding into an unfamiliar file.

---

## General Policies

### Model Download Advisory

Wherever `locus` downloads a model (any command, not just `tutor`), the user must be shown a clear advisory **before** the download begins, containing:
- The model name and its file size
- A warning that the download may be slow depending on connection speed
- The exact local path where the file will be saved (`~/.locus/models/`)
- A confirmation prompt (or clear indication that the download is starting)

This advisory must appear in all commands that trigger a model download: `overview`, `tutor`, and any future commands that use local LLMs.

---

## User Experience

### Invocation

```bash
locus tutor src/locus_cli/core/scanner.py
```

### Pre-TUI: Provisioning

Before the TUI opens, `cmd_tutor` runs the following in the terminal (not inside the TUI):

1. **Hardware profiling** — `HardwareProfiler` detects GPU type and VRAM.
2. **Tier selection** — `Provisioner.determine_tier()` picks the model tier.
3. **`n_gpu_layers` selection** — auto-selected based on `check_gpu_support()`: `-1` (full GPU offload) if GPU support is available, `0` (CPU-only) otherwise. There is no user-facing GPU/CPU selection prompt — unlike `overview`, `tutor` does not show `OverviewApp` before its own TUI opens, as two sequential TUIs would be jarring. `n_gpu_layers` is passed into `TutorSession.__init__`.
4. **Model download** — if the model is not cached, show the download advisory and download it. The TUI only opens once a model is confirmed available.

### TUI Opens Instantly

Once provisioning is complete, the TUI opens immediately — the file is rendered and the cursor sits on line 1 with no further waiting required.

### Layout — Side-by-side split

```
┌──────────────────────────┬──────────────────────────────┐
│  src/locus_cli/core/     │  EXPLANATION                 │
│  scanner.py              │                              │
│                          │  Analyzing file...           │
│    1  import os          │                              │
│    2  import sys         │                              │
│  ▶ 3  def main():        │                              │
│    4      args = parse() │                              │
│    5      run(args)      │                              │
│    ···                   │                              │
├──────────────────────────┴──────────────────────────────┤
│  ↑↓ / jk  navigate  ·  Enter / Space  reveal  ·  q quit │
└─────────────────────────────────────────────────────────┘
```

- **Left panel:** read-only code viewer with line numbers. Current line is highlighted. Scrolls to follow the cursor.
- **Right panel:** read-only explanation panel. Content changes based on session state (see Right Panel State Machine below).
- **Footer:** persistent key binding hint. The "reveal" hint is dimmed while `Analyzing file...` is active.

### Navigation & Interaction

| Key | Action |
|-----|--------|
| `j` / `↓` | Move cursor down one line |
| `k` / `↑` | Move cursor up one line |
| `Enter` / `Space` | Reveal explanation for current line |
| `q` | Quit |

Jumping to top/bottom of file (`gg`/`G`) is out of scope for v0.1.0.

### Right Panel State Machine

| State | Trigger | Right panel content |
|-------|---------|---------------------|
| `ANALYZING` | TUI opens | `Analyzing file...` |
| `READY` | Worker A completes | `Press Enter or Space to explain the current line.` |
| `GENERATING` | User presses Enter/Space on a cache miss | `Generating...` |
| `SHOWING` | Explanation available (cached or just generated) | The explanation text |
| `READY` | User navigates to a new line after viewing an explanation | `Press Enter or Space to explain the current line.` |

**Cursor movement always resets the panel to `READY` regardless of the current state** — including during `ANALYZING`, `GENERATING`, or `SHOWING`. This is the single rule that governs all cursor-triggered transitions. The table above only shows the most common paths; the `READY` reset on move applies universally.

---

## Startup Sequence

**Phase 0 (terminal, before TUI):** Provisioning — hardware profiling, model tier selection, model download if needed (with download advisory). Identical to `locus overview`.

**Phase 1 (TUI open):** File rendered instantly. Right panel shows `Analyzing file...`. Footer "reveal" hint dimmed.

**Phase 2 — Worker A (file summary):** A `threading.Thread` started by `TutorSession.__init__` feeds the full file content to the LLM and generates a structured summary (~150–250 words). When complete, the thread stores the summary in `TutorSession.file_summary` and calls `TutorSession._on_summary_ready()`, which sets an internal `threading.Event` (`_summary_ready`) and notifies `TutorApp` via a Textual `Message` posted with `app.call_from_thread(app.post_message, SummaryReady())`. `TutorApp` handles `SummaryReady` to update the right panel to `READY` state and enable the reveal hint in the footer.

**Phase 3 — Worker B (prefetch queue):** Started inside `TutorSession._on_summary_ready()` immediately after the summary is stored. Iterates lines sequentially starting from `cursor_line` at the moment Worker B begins (not always line 1 — the user may have navigated while Worker A was running). Calls `_generate_explanation(line_num)` for each uncached line and stores results in `line_cache`. The worker pauses (via `time.sleep(0.1)` poll) whenever `cached_line > cursor_line + 20`, resuming when the gap closes. This prevents wasting compute on lines the user may never reach. Lines before the starting cursor position are never prefetched — navigating backwards on a cache miss generates on demand.

---

## Context Window

The per-line explanation prompt sends the full file content on every call. To avoid exceeding the model's context window:

- **Maximum file size:** `locus tutor` refuses files larger than **500 lines or 20 KB** (whichever is hit first). `cmd_tutor` checks this before provisioning and prints a clear error if exceeded.
- **Context size:** `TutorSession` initialises the llama-cpp model with `n_ctx=8192` (doubled from the `overview` default of 4096) to accommodate the file summary + full file content in a single prompt.

These limits cover the vast majority of single-responsibility source files. Multi-file or large-file tutoring is out of scope for v0.1.0.

---

## LLM Prompt Design

### File Summary Prompt

```
You are a code tutor. Read the following file and write a structured summary for a developer who is about to read it line by line.

Cover:
1. What this file does overall (1–2 sentences)
2. Its key components — list the main classes and functions with a one-line description of each
3. Any important patterns, conventions, or design decisions a reader should know before diving in

Be concise but thorough. Target 150–250 words.

FILE: {filename}
---
{full_file_content}
```

### Per-line Explanation Prompt

```
You are a code tutor helping a developer understand a file line by line.

FILE SUMMARY:
{file_summary}

FULL FILE ({filename}):
---
{full_file_content}
---

The developer is currently on line {line_number}:
>>> {line_content}

Explain this line in plain language. If the line is part of a larger logical block (a function, class, loop, condition), also explain its role in that context. Be concise — 2–5 sentences.
```

---

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `src/locus_cli/ui/tutor_app.py` | Textual TUI — layout, key bindings, widget updates, message handlers |
| `src/locus_cli/core/tutor.py` | Session logic — file loading, summary generation, prefetch queue, `line_cache` |

### Changes to Existing Files

| File | Change |
|------|--------|
| `src/locus_cli/main.py` | Add `cmd_tutor()` handler and wire `locus tutor <file>` subcommand |

### Key Components

**`TutorSession` (`core/tutor.py`)**
- Loads and validates the file from disk
- Owns `line_cache: dict[int, str]` and `file_summary: str | None`
- Runs Worker A and Worker B as `threading.Thread` instances (not Textual workers — `TutorSession` is a plain class)
- Exposes:
  - `get_explanation(line_num) -> str | None` — returns cached result or `None`
  - `request_explanation(line_num) -> str` — generates explanation immediately (blocking), caches and returns result. Called by `TutorApp` on a cache miss inside a Textual `@work(thread=True)` worker so the UI thread is never blocked.
  - `set_cursor(line_num)` — updates internal cursor position so Worker B knows when to resume prefetching

**`TutorApp` (Textual app, `ui/tutor_app.py`)**
- Renders the side-by-side split layout
- Handles keyboard events (`j`, `k`, `↑`, `↓`, `Enter`, `Space`, `q`)
- Listens for `SummaryReady` message from `TutorSession` to transition from `ANALYZING` → `READY`
- On Enter/Space: checks `session.get_explanation(cursor)`. If cached, displays immediately. If `None`, transitions to `GENERATING` and dispatches a Textual `@work(thread=True)` worker that calls `session.request_explanation(cursor)`, then posts a result message to update the panel.
- On cursor move: calls `session.set_cursor(new_line)` and resets right panel to `READY`

**`cmd_tutor` (`main.py`)**
- Receives the file path as `args.file` (a dedicated argument, not the shared `args.path` used by other commands). The implementer must apply `Path(args.file).expanduser().resolve()` normalization explicitly — the shared path normalization block in `main()` does not cover this argument.
- Validates file path exists, is readable, and is UTF-8 decodable (rejects binary files with a clear error)
- Validates file is within size limits (≤500 lines, ≤20 KB)
- Runs provisioning (same flow as `cmd_overview`, including download advisory)
- Instantiates and runs `TutorApp`

---

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| File not found | Print error, exit before provisioning |
| File is binary (not UTF-8) | Print error, exit before provisioning |
| File exceeds size limit | Print error (with actual line/byte count), exit before provisioning |
| Model not downloaded | Surface provisioning/download flow with advisory (same as `overview`) |
| Cache miss on reveal | Transition to `GENERATING`, generate on demand via `@work` worker, update panel when done |
| LLM error during generation | Show `Could not generate explanation. Press Enter to retry.` in right panel |

---

## Out of Scope (v0.1.0)

- Follow-up questions / interactive chat (planned for a future version)
- Multi-file context (tutor operates on a single file)
- Cloud LLM providers (local only, same as `overview`)
- Syntax highlighting in the code viewer
- Jump-to-top / jump-to-bottom shortcuts
- Files larger than 500 lines or 20 KB
