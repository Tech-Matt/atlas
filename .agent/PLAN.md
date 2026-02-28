# Locus Implementation Plan

## What is Locus? Or what is Locus going to be?
Locus is a hybrid python terminal app. Hybrid because it can support normal terminal output formats or a graphical TUI built with Textual and Rich frameworks. 

The objective of the app is to create a fast, safe tool to get a quick grasp of a foreign or unkown codebase. Locus is going to feature many commands, for example to show a tree of the codebase, to give summaries about folders structure and relationships, and ultimately to give accurate informations about the whole codebase, using auto-downloaded open source LLMs. 

Many features of the app are still matter of brainstorming so any useful suggestion is welcomed.

## 1) Product Direction and Constraints
- **Goal:**: Free, 100% private, local-LLM codebase cartographer for the terminal.
- **Constraints:** Lightweight, fast, small, cross-platform, local-first (llama.cpp) with optional cloud support, responsive UI.

## 2) Current State (as of 2026-02-27)
**Done:**
- Mapping for `locus tree` (`core/map.py`), hardware profiling (`core/profiler.py`), basic provisioner (`core/provisioner.py`).
- Initial Textual app shell (`ui/app.py`)
- `locus tree` fully wired with `--depth`, `--max-files`, `--ignore` flags.
- Type hints and `mypy` static checks
- Unit tests for `locus tree` passing
(`tests/test_tree.py`)
- PyPI packaging: `locus-cli` v0.1.0a2 released.
- CI/CD publish workflow (`.github/workflows/publish.yml`)

**Missing / WIP:**
- `ui/style.tcss` still empty
- `locus tree` needs speedup and or real time printing
- `locus overview` command (not yet designed, or implemented, no idea on what to do with this command)
- Need to think about other useful commands both "static" and with "LLMs"
- Inference runtime (llama.cpp management, prompt pipeline).
- Cloud provider integrations (OpenAI, Claude, Gemini)
- Repository analysis pipeline
- Responsive cool looking TUI
- CI/CD test workflow for different archs (Windows, MAC OS, Linux)

## 3) Target Architecture
Still to be decided, dependent of what the app needs to do, a first implementation could be:

- **`core/`**: `scanner.py`, `analyzer.py`, `graph.py`, `summarizer.py`, `cache.py`.
- **`core/inference/`**: `providers/` (local_llama_cpp, openai, anthropic, gemini).
- **`cli/`**: `app.py`, `commands/` (tree, overview, etc.).
- **`ui/`**: `views/` (tree, overview, relationships), `widgets/`.

## 4) Roadmap

**Phase 0: Foundation (WIP)**
- Config loader (`~/.locus/config.toml`), logging, standardized errors.

**Phase 1: CLI Skeleton (In progress)**
- ✅ `locus tree` implemented with depth, max_files, and ignore flags.
- ⏳`locus overview` to be designed and implemented. Need to chose what this command does.
- ⏳ Need to think about other future commands and namings.
- ⏳ Progressive rendering for `locus tree` - print tree nodes to stdout as they are discovered, instead of waiting for the full traversal to complete. This is critical for large repos.
- ⏳ Need to think about a way to show large trees with `locus tree` when the user needs to scroll to much and could lose the idea of what the codebase does.

**Phase 2: Intelligence Pipeline**
- Fast scanner (respects `gitignore`), relationship extractor, caching and other stuff that could be useful to understand a codebase

**Phase 3: Inference Backends**
- Complete `Provisioner` (downloads/extract binaries)
- Local llama.cpp runtime + Cloud provider adapters

**Phase 4: Textual TUI Expansion**
- Still to be decided

**Phase 5: UX & Performance**
- Progressive rendering, timeouts, startup checks, benchmarks, better performance and speed overall.

**Phase 6: Quality & Testing**
- Unit/Integration tests, CI matrix.

**Phase 7: Documentation**
- Update README, add troubleshooting and provider docs.

## 5) Definition of Done (v0.1.0)
No idea for now