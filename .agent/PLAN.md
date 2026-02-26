# Locus Implementation Plan

## 1) Product Direction & Guardrails
- **Goal:** Free, 100% private, local-LLM codebase cartographer for the terminal.
- **Constraints:** Lightweight, fast, local-first (llama.cpp) with optional cloud, responsive UI.

## 2) Current State (as of 2026-02-27)
**✅ Done:**
- Core mapping (`core/map.py`), hardware profiling (`core/profiler.py`), basic provisioner (`core/provisioner.py`).
- Initial Textual app shell (`ui/app.py`, `ui/style.tcss`).
- `locus tree` fully wired with `--depth`, `--max-files`, `--ignore` flags.
- Type hints and `mypy` static checks passing across all modules.
- Unit tests for `LocusMap` passing (`tests/test_tree.py`).
- PyPI packaging: `locus-cli` v0.1.0a2 released.
- CI/CD publish workflow (`.github/workflows/publish.yml`).

**❌ Missing / WIP:**
- `locus overview` command (not yet designed or implemented).
- Progressive rendering for `locus tree` on large repos (currently blocks until fully built).
- Inference runtime (llama.cpp management, prompt pipeline).
- Cloud provider integrations (OpenAI/Claude/Gemini).
- Repository analysis pipeline (scanner, analyzer, cache).
- Multi-view TUI.

## 3) Target Architecture
- **`core/`**: `scanner.py`, `analyzer.py`, `graph.py`, `summarizer.py`, `cache.py`.
- **`core/inference/`**: `providers/` (local_llama_cpp, openai, anthropic, gemini).
- **`cli/`**: `app.py`, `commands/` (tree, overview, etc.).
- **`ui/`**: `views/` (tree, overview, relationships), `widgets/`.

## 4) Phased Implementation Roadmap

**Phase 0: Foundation (WIP)**
- Config loader (`~/.locus/config.toml`), logging, standardized errors.

**Phase 1: CLI Skeleton (In Progress)**
- ✅ `locus tree` implemented with depth, max-files, and ignore flags.
- ⏳ `locus overview` — static codebase stats (file counts by language, largest folders).
- ⏳ Progressive rendering for `locus tree` — print tree nodes to stdout as they are discovered, instead of waiting for the full traversal to complete. This is critical for large repos like the Linux kernel source.

**Phase 2: Intelligence Pipeline**
- Fast scanner (respects `.gitignore`), relationship extractor, caching.

**Phase 3: Inference Backends**
- Complete `Provisioner` (download/extract binaries).
- Local llama.cpp runtime + Cloud provider adapters.

**Phase 4: Textual TUI Expansion**
- Multi-view app (Tree, Overview, Relationships), async workers, loading states.

**Phase 5: UX & Performance**
- Progressive rendering, timeouts, startup checks, benchmarks.

**Phase 6: Quality & Testing**
- Unit/Integration tests, CI matrix.

**Phase 7: Documentation**
- Update README, add troubleshooting and provider docs.

## 5) Command Rollout
- **Milestone A:** `tree`, `overview`
- **Milestone B:** `summarize [path]`, `relationships`
- **Milestone C:** `tui`, `doctor`
- **Milestone D:** `cache`, `models`

## 6) Definition of Done (v0.1 Alpha)
- Installable via PyPI (`locus-cli`).
- `tree` and `overview` stable on large repos.
- Summary generation works (local preferred).
- Basic TUI navigation works.
- Core tests and CI passing.
