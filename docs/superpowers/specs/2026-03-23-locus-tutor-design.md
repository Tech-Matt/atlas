# locus tutor — Design Spec

**Date:** 2026-03-23
**Status:** Approved

---

## Overview

`locus tutor <file>` is an interactive, line-by-line code tutoring command for `locus`. The user navigates through a file one line at a time in a Textual TUI. On demand, the tutor generates a plain-language explanation of the current line — aware of the full file context — and displays it in a side panel. Explanations are pre-generated in the background so the experience feels instant.

**Primary use case:** Re-understanding code you've lost track of (AI-generated, inherited, or simply forgotten), or onboarding into an unfamiliar file.

---

## User Experience

### Invocation

```bash
locus tutor src/locus_cli/core/scanner.py
```

The TUI opens immediately. The file is rendered in the left panel. The cursor starts on line 1.

### Layout — Side-by-side split

```
┌──────────────────────────┬──────────────────────────────┐
│  src/locus_cli/core/     │  EXPLANATION                 │
│  scanner.py              │                              │
│                          │  Analyzing file...           │
│    1  import os          │  (ready once summary loads)  │
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
- **Right panel:** read-only explanation panel. Shows `Analyzing file...` during startup. Updates when the user reveals an explanation.
- **Footer:** persistent key binding hint.

### Navigation & Interaction

| Key | Action |
|-----|--------|
| `j` / `↓` | Move cursor down one line |
| `k` / `↑` | Move cursor up one line |
| `Enter` / `Space` | Reveal explanation for current line |
| `q` | Quit |

---

## Startup Sequence

The TUI opens instantly — no waiting before the file is displayed.

**Background Worker A — File Summary**
Immediately after the TUI opens, a `@work(thread=True)` Textual worker feeds the full file content to the local LLM and requests a structured summary. This summary covers:
- What the file does overall
- Its key components (main classes, functions, and their roles)
- Any important patterns or design decisions a reader should know upfront

Target length: ~150–250 words. Stored in session memory for the duration of the session.

The right panel shows `Analyzing file...` until the summary is ready. Once it arrives, the panel transitions to `Press Enter or Space to explain the current line.`

**Background Worker B — Prefetch Queue**
Starts immediately after Worker A completes. Generates explanations for each line sequentially, storing results in `line_cache: dict[int, str]`. The worker runs continuously through the file.

Because the user spends several seconds reading each explanation, Worker B stays ahead of the cursor in normal linear reading. On a cache miss (user jumps ahead), the explanation is generated on demand.

---

## LLM Prompt Design

### File Summary Prompt

```
You are a code tutor. Read the following file and write a structured summary for a developer who is about to read it line by line.

Cover:
1. What this file does overall (1–2 sentences)
2. Its key components — list the main classes and functions with a one-line description of each
3. Any important patterns, conventions, or design decisions a reader should know before diving in

Be concise but thorough. Target ~200 words.

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
| `src/locus_cli/ui/tutor_app.py` | Textual TUI — layout, key bindings, widget updates |
| `src/locus_cli/core/tutor.py` | Session logic — file loading, summary generation, prefetch queue, `line_cache` |

### Changes to Existing Files

| File | Change |
|------|--------|
| `src/locus_cli/main.py` | Add `cmd_tutor()` handler and wire `locus tutor <file>` subcommand |

### Key Components

**`TutorApp` (Textual app, `ui/tutor_app.py`)**
- Renders the side-by-side split layout
- Handles keyboard events (`j`, `k`, `↑`, `↓`, `Enter`, `Space`, `q`)
- Calls into `TutorSession` for explanations
- Updates the right panel reactively

**`TutorSession` (`core/tutor.py`)**
- Loads the file from disk
- Owns `line_cache: dict[int, str]`
- Exposes `get_explanation(line_num) -> str | None` — returns cached result or `None` if not yet ready
- Runs Worker A (summary) and Worker B (prefetch) as background threads
- Prefetch worker iterates lines sequentially, skips already-cached lines, pauses if it gets too far ahead of the cursor (to avoid wasting compute on lines the user may never reach)

**`cmd_tutor` (`main.py`)**
- Validates the file path exists and is readable
- Instantiates and runs `TutorApp`

---

## Error Handling

- **File not found:** print error and exit before launching TUI
- **Unsupported file type:** no restriction — tutor works on any text file
- **LLM not available / model not downloaded:** surface the same provisioning flow as `locus overview` (model download prompt before TUI opens)
- **Cache miss on explanation reveal:** show a brief `Generating...` indicator in the right panel, generate on demand, update when done

---

## Out of Scope (v0.1.0)

- Follow-up questions / interactive chat (planned for a future version)
- Multi-file context (tutor operates on a single file)
- Cloud LLM providers (local only, same as `overview`)
- Syntax highlighting in the code viewer (nice-to-have, not required)
