# `locus overview` — Feature Spec

## Purpose
Provide an AI-generated narrative summary of a codebase using a local LLM.
No cloud API keys required. Runs entirely on-device via llama.cpp.

## Command Signature
```
locus overview [PATH] [--ignore PATTERN]... [--model-tier 1|2|3|4]
```

## Output
A short AI-generated report containing:
- **What this project does** — 1-2 paragraph plain-English summary
- **Main components** — bullet list of key modules/directories and their roles
- **Entry points** — how to run or use the project
- **Notable patterns** — architecture style, test coverage, CI setup

## Pipeline (4 stages)

### Stage 1 — Static scan (reuses `locus info`)
Run `scan(root)` to get `InfoResult`: languages, entry points, project type, etc.

### Stage 2 — Context extraction (`core/extractor.py`)
Build a compact `ProjectContext` to feed to the LLM:
- README.md content (truncated to ~3000 chars)
- Top-2-level directory tree (as plain text)
- First 60 lines of each entry point file
- First 30 lines of the dependency manifest (pyproject.toml, package.json, etc.)
- Language breakdown and project type (from InfoResult)

Total context target: <4000 tokens to fit small models (0.5B–1.5B).

### Stage 3 — Model provisioning (`core/provisioner.py`)
- Profile hardware via `HardwareProfiler` → determine tier (1–4)
- Check if model GGUF exists in `~/.locus/models/`
- If not: download from HuggingFace with a Rich progress bar
- Check if llama-server binary exists in `~/.locus/bin/`
- If not: download and extract the llama.cpp release for this platform/GPU

### Stage 4 — Inference (`core/inference.py`)
- Start `llama-server` as a subprocess (OpenAI-compatible HTTP API on localhost)
- Send a single chat completion request with the project context as the prompt
- Stream the response tokens to the terminal via Rich Live
- Shut down the subprocess when done

## Prompt template (Stage 4 input)
```
You are a senior software engineer. Analyse the following codebase context
and write a concise overview report. Be factual and specific.

Project type: {project_type}
Primary language: {primary_language}
Dependency file: {dependency_file}

Directory structure:
{tree_summary}

README:
{readme}

Key file snippets:
{snippets}

Write the overview report now.
```

## Edge Cases
- No README → skip that section of the prompt
- No entry points found → skip snippets
- Model not yet downloaded → show download progress, then proceed
- llama-server fails to start → show a clear error with instructions

## Out of Scope (for now)
- Cloud API backends (OpenAI, Anthropic, Gemini) — Phase 2
- Multi-file deep analysis / AST parsing — Phase 3
- Caching inference results — Phase 3