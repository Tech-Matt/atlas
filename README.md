<div align="center">

# LOCUS 🗺️

**Regain control of your codebase.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/locus-cli.svg)](https://pypi.org/project/locus-cli/)

</div>

---

## The Problem

You handed your coding to AI agents. They shipped fast, tests pass, everything runs — but you no longer fully understand your own codebase. Or maybe you just inherited a large project and don't know where to begin.

Either way, the code works. You just don't *own* it anymore.

## The Solution

Locus is a terminal tool built specifically for this moment. It gives you a structured way to re-explore, understand, and get back in control of a codebase — whether it's yours or someone else's.

It maps your project's structure, breaks down what's in it, and uses a **local LLM running entirely on your machine** to generate a plain-language overview. No cloud, no API keys, no sending your proprietary code anywhere.

---

## Commands

```bash
# Visual tree of the project structure
locus tree

# Static breakdown: languages, file counts, entry points, largest files
locus info

# AI-generated overview of the whole codebase (runs a local LLM)
locus overview

# Interactive line-by-line code tutor (local LLM)
locus tutor src/main.py
```

All commands accept a `path` argument and `--ignore` flags:

```bash
locus tree /path/to/project --depth 3 --ignore build --ignore dist
locus info /path/to/project --ignore node_modules
locus overview /path/to/project
```

---

## Local-first, private by default

Locus automatically detects your hardware (Apple Silicon, NVIDIA, AMD, or CPU-only) and downloads the right model size for your machine. The model runs locally via `llama-cpp-python`. Your code never leaves your machine.

No Docker. No manual setup. Just `pip install locus-cli` and run.

---

## Installation

```bash
pip install locus-cli
```

Or from source:

```bash
git clone https://github.com/Tech-Matt/locus.git
cd locus
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

---

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

---

## Platform support

| Platform | Status |
|---|---|
| macOS (Apple Silicon) | Supported |
| Linux | Supported |
| Windows | Supported |
| macOS (Intel) | Not yet |

---

## Roadmap

- [x] `locus tree` — recursive directory tree with gitignore support
- [x] `locus info` — static codebase snapshot (languages, file counts, project type, largest files)
- [x] `locus overview` — AI-powered summary using a local LLM (auto-downloads the right model)
- [x] Hardware profiling — Apple Silicon, NVIDIA, AMD, CPU-only detection
- [x] Progressive rendering — live output while scanning
- [ ] `locus ask` — ask a natural language question about the codebase
- [x] `locus tutor` — interactive line-by-line code walkthrough with an AI tutor

---

<div align="center">
Made with ❤️ by <a href="https://github.com/Tech-Matt">Tech-Matt</a>
</div>
