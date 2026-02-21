<div align="center">

# ATLAS

**The free, 100% private, local-LLM codebase cartographer for your terminal.**

[![Python 3.x](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Work in Progress](https://img.shields.io/badge/Status-WIP-orange.svg)]()

*Stop paying for expensive API keys just to understand a codebase. Atlas is a lightweight terminal tool that automatically downloads and runs architecture-optimized local LLMs to instantly map and summarize large codebases—for free, and 100% privately.*

</div>

---

## Why Atlas?

Diving into a massive codebase like the Linux Kernel or a legacy enterprise app can be overwhelming. **Atlas** provides instant visual overviews and directory trees right in your terminal, helping you map out the structure before you deep dive into the code.

### Free, Open, Local Intelligence
You shouldn't have to pay for expensive Gemini, Claude, or OpenAI API keys just to understand a codebase. Atlas dynamically profiles your PC's hardware (Apple Silicon, NVIDIA, AMD, or CPU-only) and automatically downloads and runs **architecture-optimized local LLMs**. You get instant, private folder summaries running entirely on your own machine—for free. *(Cloud APIs are still supported if you prefer them).*

- **Zero-Friction:** Just do `pip install atlas` and run `atlas`. No Docker, no manual model downloading.
- **Fast & Native:** A fast TUI built with `Textual` and `Rich`.
- **Private by Default:** Your proprietary code never leaves your machine unless you explicitly configure a cloud provider.

---

## Installation

*Note: Atlas is currently in active development. A v0.1 release is coming soon!*

```bash
git clone https://github.com/Tech-Matt/atlas.git
cd atlas
python -m venv myEnv
source myEnv/bin/activate  # Windows: `myEnv\Scripts\activate`
pip install -r requirements.txt
python main.py
```

---

## Usage

Run `atlas` in any directory you want to explore:

```bash
cd /path/to/massive/codebase
atlas
```

**Keybindings:**
- `j` / `k` : Scroll Down / Up
- `d` : Toggle Dark/Light Mode
- `q` : Quit Atlas
- `A` : (Coming Soon) Generate a quick summary for the selected folder

---

## Roadmap

- [x] **Phase 1: Visual Engine** (Recursive parsing, smart filtering, TUI scaffolding)
- [ ] **Phase 2: Hardware Profiling** (Native GPU/RAM detection, model mapping)
- [ ] **Phase 3: Local Summaries** (Local inference engine, TUI integration)
- [ ] **Phase 4: Testing & Hardening** (Unit tests, CI/CD pipeline)
- [ ] **Phase 5: Packaging** (PyPI release, zero-dependency binaries)

---

<div align="center">
Made with ❤️ by <a href="https://github.com/Tech-Matt">Tech-Matt</a>
</div>
