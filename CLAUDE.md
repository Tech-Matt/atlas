# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode (required before running `locus` from source)
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_scanner.py

# Run a single test by name
pytest tests/test_tree.py::test_tree_progress_callback_is_called

# Type checking
mypy src/locus_cli
```

Tests use `tmp_path` (pytest fixture) for all filesystem operations — no real disk paths.

## Architecture

The CLI entry point is `src/locus_cli/main.py` (`main()` → `build_parser()` → subcommand handler). Each command is a plain function `cmd_*` that receives an `argparse.Namespace`.

**Commands and their data flow:**

- **`locus tree`** → `LocusMap` (`core/map.py`) → returns a `rich.tree.Tree` rendered to the console. `LocusMap` does a recursive DFS walk, respects `.gitignore`, and supports an `on_progress: Callable[[], None]` callback fired after each directory.

- **`locus info`** → `scan()` (`core/scanner.py`) → returns `InfoResult` (file counts, language breakdown, heuristics, largest files) → rendered by `ui/info_renderer.py`. `scan()` uses an iterative DFS via an explicit stack. `on_progress` receives the partial `InfoResult`.

- **`locus overview`** — full pipeline:
  1. `scan()` → `extract_context()` (`core/extractor.py`) → `ProjectContext` (LLM-ready: README, tree summary, entry-point snippets, dependency manifest)
  2. `HardwareProfiler` (`core/profiler.py`) detects GPU type + VRAM → `Provisioner.determine_tier()` picks model tier 1–4
  3. `OverviewApp` (Textual TUI, `ui/overview_app.py`) — setup screen shows hardware, user picks GPU/CPU, then a `@work(thread=True)` worker runs the pipeline:
     - `Provisioner.download_model()` streams GGUF from HuggingFace to `~/.locus/models/` if not cached
     - `stream_overview()` (`core/inference.py`) loads via `llama-cpp-python` and streams tokens back via `on_token` callback

**Key design notes:**

- `scanner.py` and `map.py` both implement `.gitignore` parsing independently (no shared utility) — `scanner.py` is intentionally self-contained to avoid circular imports.
- GPU layers: `n_gpu_layers=-1` = full GPU offload, `0` = CPU only. The `check_gpu_support()` function probes `llama_supports_gpu_offload()` at runtime to detect whether `llama-cpp-python` was compiled with GPU support.
- Models are stored in `~/.locus/models/`, binaries in `~/.locus/bin/`. Downloads are atomic (write to `.tmp`, rename on success).
- `ui/console.py` exports a shared `console` instance and `supports_unicode()` used across the codebase for terminal compatibility.
- The `llama-cpp-python` package in `pyproject.toml` is CPU-only by default. GPU support requires reinstalling with a specific `--extra-index-url` (NVIDIA CUDA or AMD ROCm) — see `inference.py` for the hints.