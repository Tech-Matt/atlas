<div align="center">

# LOCUS 🗺️

**The free, 100% private, local-LLM codebase cartographer for your terminal.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/locus-cli.svg)](https://pypi.org/project/locus-cli/)

*Stop paying for expensive API keys just to understand a codebase. Locus is a lightweight terminal tool that automatically downloads and runs architecture-optimized local LLMs to instantly map and summarize large codebases—for free, and 100% privately.*

</div>

---

## Why Locus?
I wanted a tool to explore new and large codebases (like the *Linux Kernel* source code 😄), with an intuitive and powerful UI. **Locus** provides instant visual overviews and directory trees right in your terminal, helping you map out the structure before you deep dive into the code.

### Free, Open, Local Intelligence
You shouldn't have to pay for expensive Gemini, Claude, or OpenAI API keys just to understand a codebase. **Locus dynamically profiles** your PC's hardware (Apple Silicon, NVIDIA, AMD GPU, or CPU-only) and automatically downloads and runs **architecture-optimized local LLMs**. You get instant and private folder summaries running entirely on your own machine—for free. *(Cloud APIs are still supported if you prefer them).*

- **Zero-Friction:** Just do `pip install locus-cli` and run `locus`. No Docker, no manual model downloading. (Still to be packaged as of now)
- **Fast & Native:** A fast TUI built with `Textual` and `Rich`.
- **Private by Default:** Your proprietary code never leaves your machine unless you explicitly configure a cloud provider.

### Current Platform Support
- **macOS (Apple Silicon / arm64):** Supported
- **macOS (Intel / x86_64):** Not supported yet
- **Linux:** Supported
- **Windows:** Supported

---

## Installation

```bash
pip install locus-cli
```

Or to run from source:

```bash
git clone https://github.com/Tech-Matt/locus.git
cd locus
python -m venv .venv
source .venv/bin/activate  # Windows: `.venv\Scripts\activate`
pip install -e .
```

---

## Usage

```bash
# Show a tree of the current directory
locus tree

# Show a tree of a specific path, with custom depth and ignore rules
locus tree /path/to/codebase --depth 3 --ignore build --ignore dist

# Show a static codebase summary (languages, project type, largest files)
locus info

# Show info for a specific path, ignoring extra folders
locus info /path/to/codebase --ignore build --ignore dist

# Print version
locus --version
```

---

## Roadmap

- [x] **Recursive tree mapping** with smart filtering and file caps
- [x] **Hardware profiling** (Apple Silicon, NVIDIA, AMD, CPU-only detection)
- [x] **`locus tree` CLI command** (depth, max-files, ignore flags)
- [x] **PyPI packaging** (`pip install locus-cli`)
- [x] **`locus info`** — static codebase snapshot (file counts, language breakdown, project type, largest files)
- [x] **Progressive rendering** — live progress display while scanning for both `tree` and `info`
- [x] **File type icons** — per-extension emoji in tree view with ASCII fallback for legacy terminals
- [ ] **`locus overview`** — AI-powered codebase summary using a local LLM
- [ ] **Local LLM inference** — auto-download and run architecture-optimized models (llama.cpp)
- [ ] **TUI** — full interactive terminal UI

---

<div align="center">
Made with ❤️ by <a href="https://github.com/Tech-Matt">Tech-Matt</a>
</div>
