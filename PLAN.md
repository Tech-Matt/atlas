# Locus Implementation Plan

This document defines the next implementation steps for **Locus** as an incremental terminal app, packaged as `locus-cli` on PyPI.

## Agent Directives
Developer wants to actually learn things and not just copy-paste. Unless otherwise specified, always provide skeletons or snippets of code rather than full implementations. This is really important. 
Provide also clear explanations to why you are doing things and about what kind of thing you are suggesting.

## 1) Product Direction (Scope Guardrails)

- Keep Locus lightweight and fast (low RAM/CPU overhead, minimal dependencies).
- Prioritize local-first architecture (llama.cpp + local GGUF models) with optional cloud backends.
- Implement commands incrementally; each command should be useful on its own.
- Keep UI responsive at all times, even on very large repositories.

## 2) Current State Snapshot

_Status updated from repository state on 2026-02-25._

### Implemented
- Recursive tree mapping with filtering and file caps (`core/map.py`).
- Hardware profiling for RAM + basic accelerator detection (`core/profiler.py`).
- Basic model/binary provisioning matrix started (`core/provisioner.py`).
- Initial Textual app shell + keybindings + stylesheet wiring (`ui/app.py`, `ui/style.tcss`).
- Packaging metadata exists in `pyproject.toml`:
  - project name `locus-cli`
  - alpha version `0.1.0a1`
  - console script entrypoint set to `locus = locus_cli.main:main`
  - package discovery configured for `src/`
- Dependencies declared in both `requirements.txt` and `pyproject.toml`.

### Missing / Incomplete
- CLI entrypoint and subcommand architecture (`main.py` is empty).
- Functional `locus` command behavior (entrypoint points to `main`, but no implementation yet).
- Inference runtime integration (llama.cpp process management, prompt pipeline, parsing).
- Cloud provider integrations (OpenAI / Claude / Gemini adapters).
- Repository analysis pipeline for summaries + relationship graphing.
- TUI views beyond a single static map panel.
- Scanner/analyzer/cache modules from target architecture.
- Automated tests are not yet implemented (`tests/test_map.py` is empty).
- Packaging validation and publish workflow are implemented (`.github/workflows/publish.yml`, `dist/` artifacts present).
- README usage/docs are not yet aligned with the current package entrypoint and command state.

## 3) Target Architecture (Incremental)

### Core packages to establish
- `core/scanner.py`: fast file-system scan, ignore rules, metadata extraction.
- `core/analyzer.py`: module/folder relationship extraction and summary inputs.
- `core/graph.py`: directory/module relationship graph (networkx-backed).
- `core/summarizer.py`: orchestration for local/cloud summarization.
- `core/inference/`:
  - `providers/local_llama_cpp.py`
  - `providers/openai_provider.py`
  - `providers/anthropic_provider.py`
  - `providers/gemini_provider.py`
  - shared provider interface + config objects.
- `core/cache.py`: lightweight cache for scan and summary artifacts.

### CLI/TUI packages to establish
- `cli/app.py` (or `main.py`): command router for `locus <command>`.
- `cli/commands/`: one file per command (`tree`, `overview`, etc.).
- `ui/views/`: modular Textual screens (tree, overview, relationships, status).
- `ui/widgets/`: reusable widgets (loading/status/errors/summary cards).

## 4) Phased Implementation Steps

### Phase Progress Snapshot (as of 2026-02-25)
- **Phase 0 — Project Foundation:** **Partial**
  - Done: model/bin directory foundations in `Provisioner` (`~/.locus` paths).
  - Missing: config loader, precedence rules, logging strategy, standardized errors.
- **Phase 1 — CLI Skeleton + First Useful Commands:** **Not started**
  - `main.py` is still empty, no `tree` / `overview` CLI commands yet.
- **Phase 2 — Fast Codebase Intelligence Pipeline:** **Not started**
  - Planned modules (`scanner`, `analyzer`, `cache`) not present.
- **Phase 3 — Inference Backends (Local First):** **Started (early)**
  - Done: initial model/binary mapping tables and hardware tier logic.
  - Missing: binary preference implementation, download/integrity/extraction flow, runtime orchestration.
- **Phase 4 — Textual TUI Expansion:** **Started (early)**
  - Done: single-view app shell, keybindings, basic tree rendering.
  - Missing: multi-view architecture, background workers, loading/error states.
- **Phase 5 — UX + Performance Hardening:** **Not started**
- **Phase 6 — Quality and Testing:** **Not started**
- **Phase 7 — Documentation:** **Partial** (README exists, but command-level docs need realignment)

## Phase 0 — Project Foundation
- Define config locations (`~/.locus/config.toml`, cache, model, binary dirs).
- Add structured settings loader (env + config file + CLI flags precedence).
- Add logging strategy (quiet by default, `--verbose` for diagnostics).
- Standardize error model and user-facing failure messages.

**Exit criteria**
- App can load configuration and print diagnostics in a deterministic way.

## Phase 1 — CLI Skeleton + First Useful Commands
- Build CLI parser and command registry.
- Implement `locus tree` (existing tree logic integrated via CLI options: depth, ignore, max files).
- Implement `locus overview` with lightweight static stats:
  - file counts per language
  - largest folders
  - rough dependency indicators (without LLM yet)
- Add machine-readable output option (`--json`) for both commands.

**Exit criteria**
- `locus tree` and `locus overview` work from terminal without TUI.

## Phase 2 — Fast Codebase Intelligence Pipeline
- Implement scalable scanner with:
  - ignore handling (`.gitignore` + app defaults + user overrides)
  - extension/language classification
  - chunked traversal to handle very large repositories
- Build relationship extractor:
  - folder-to-folder references (imports/includes)
  - top modules and hotspots
- Persist intermediate artifacts to cache (hash by repo path + commit/mtime).

**Exit criteria**
- Scanner and analyzer can process large repos quickly and reuse cached outputs.

## Phase 3 — Inference Backends (Local First)
- Complete `Provisioner`:
  - binary selection matrix implementation
  - download and integrity checks (checksum)
  - extraction + version pinning
- Add local inference runtime:
  - llama.cpp executable discovery
  - process lifecycle management
  - prompt templates for folder/repo summaries
- Add provider abstraction + cloud adapters:
  - OpenAI, Anthropic, Gemini using optional API keys
  - backend fallback strategy (`local -> cloud` or user-selected)

**Exit criteria**
- `locus overview --summarize` generates summaries with chosen provider.

## Phase 4 — Textual TUI Expansion
- Convert UI into multi-view application:
  - Tree View
  - Overview View
  - Relationships View
  - Summary Panel
- Add non-blocking data loading (workers/background tasks).
- Add keyboard navigation + status footer + loading/error states.
- Ensure large-output rendering remains smooth (virtualization/paging where needed).

**Exit criteria**
- TUI remains responsive while scanning/analyzing/summarizing large repositories.

## Phase 5 — UX + Performance Hardening
- Introduce progressive rendering (show partial results early).
- Add timeout/retry/circuit-breaker behavior for providers.
- Add startup checks for missing binaries/models and guided remediation.
- Add benchmark script for scan speed and memory footprint.

**Exit criteria**
- Stable behavior on large repos and constrained machines.

## Phase 6 — Quality and Testing
- Add unit tests for:
  - scanner filters/limits
  - profiler/provisioner decision logic
  - command argument parsing
- Add integration tests for `locus tree` and `locus overview`.
- Add snapshot tests (or textual pilot tests) for major TUI outputs.
- Add CI workflow: lint, test matrix, packaging checks.

**Exit criteria**
- CI green on Linux/macOS/Windows for supported Python versions.

## Phase 7 — Documentation
- Update README usage to match implemented commands.
- Add docs for providers, privacy model, and configuration examples.
- Add troubleshooting guide (model download, missing GPU tools, path issues).

**Exit criteria**
- New users can install, run, and troubleshoot without source diving.

## 5) Incremental Command Roadmap

### Milestone A (first release-ready command set)
- `locus tree`
- `locus overview`

### Milestone B
- `locus summarize [path]`
- `locus relationships`

### Milestone C
- `locus tui`
- `locus doctor` (environment and provider diagnostics)

### Milestone D
- `locus cache` (inspect/clear cache)
- `locus models` (list/download/remove local models)

## 6) Responsiveness Requirements

- Never block the UI thread for scan/analyze/summarize operations.
- Stream intermediate results and show deterministic progress states.
- Enforce upper bounds on in-memory objects for very large trees.
- Prefer lazy loading of deep nodes and detailed summaries.

## 7) PyPI Name Reservation Subplan (Do This Now)

Goal: publish a minimal but valid package quickly to reserve `locus-cli`, while clearly marking pre-release status.

### Immediate tasks
- ✅ Add packaging metadata (`pyproject.toml`) with:
  - project name `locus-cli`
  - version `0.1.0a1` (or similar alpha pre-release)
  - description, license, readme, dependencies
  - console script entrypoint: `locus = locus_cli.main:main`
- ⏳ Implement a minimal `main.py` entrypoint that:
  - prints version/help
  - exposes at least one working command (`tree`) or “WIP” notice for unimplemented commands
- ✅ Include essential files in distribution (`README.md`, `LICENSE`).
- ✅ Build and validate package:
  - `python -m build`
  - `twine check dist/*`
- ✅ Publish with trusted workflow or API token to PyPI.

### Release safety notes
- Use alpha/dev version suffix until core features are stable.
- Clearly label README and CLI output as WIP to set user expectations.
- Avoid shipping broken commands silently; return explicit “not implemented yet”.

### Post-reservation follow-up
- ✅ Set up release workflow (`.github/workflows/publish.yml`).
- Add TestPyPI pipeline (optional preflight channel before production PyPI).
- Add semantic versioning strategy and changelog process.

## 8) Suggested Near-Term Execution Order (Next 2–3 Weeks)

1. ✅ Package skeleton + reserve `locus-cli` on PyPI.
2. Implement robust CLI skeleton + `locus tree` + `locus overview`.
3. Build scanner/analyzer cache pipeline.
4. Complete local llama.cpp provisioning + inference summary flow.
5. Expand TUI into multi-view responsive interface.
6. Add tests + CI hardening.

## 9) Definition of Done for “Useful v0.1 Alpha”

- Installable from PyPI as `locus-cli`.
- `locus tree` and `locus overview` stable on large repositories.
- Optional summary generation works with at least one provider (local preferred).
- Basic TUI available and responsive for navigation.
- Core tests and CI in place for critical paths.

