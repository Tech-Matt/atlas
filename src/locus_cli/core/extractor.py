from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

from .scanner import InfoResult, _EXTENSION_TO_LANGUAGE

# Maximum characters to read from the README before truncating.
_README_MAX_CHARS = 3000
# Maximum lines to read from each key file snippet.
_SNIPPET_MAX_LINES = 60
# Maximum lines to read from the dependency manifest.
_MANIFEST_MAX_LINES = 30
# Common README filenames to probe, in order of preference.
_README_NAMES = ("README.md", "README.rst", "README.txt", "README")


@dataclass
class ProjectContext:
    """
    Compact, LLM-ready context extracted from a codebase.
    Passed directly to the prompt builder in inference.py.
    """
    project_type: str                         # e.g. "Python Package"
    primary_language: str                     # top language by file count
    dependency_file: str | None               # e.g. "pyproject.toml"
    readme: str | None                        # README content, possibly truncated
    tree_summary: str                         # top-2-level directory listing
    # List of (relative_path, content_snippet) for key files
    snippets: list[tuple[str, str]] = field(default_factory=list)


def _read_truncated(path: Path, max_chars: int) -> str:
    """Read a file and return its content, truncated to max_chars."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[:max_chars] + "\n... (truncated)"
        return text
    except OSError:
        return ""


def _read_lines(path: Path, max_lines: int) -> str:
    """Read up to max_lines from a file, return as a single string."""
    try:
        lines = []
        with path.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... (truncated at line {max_lines})\n")
                    break
                lines.append(line)
        return "".join(lines)
    except OSError:
        return ""


def _build_tree_summary(root: Path, result: InfoResult) -> str:
    """
    Build a simple top-2-level directory listing as plain text.
    Does not re-walk the filesystem — derives structure from the root only.
    """
    lines: list[str] = [f"{root.name}/"]
    try:
        entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError:
        return lines[0]

    for entry in entries:
        if entry.name.startswith(".") or entry.name in ("__pycache__", "node_modules", ".venv", "venv"):
            continue
        if entry.is_dir():
            lines.append(f"  {entry.name}/")
            try:
                sub = sorted(entry.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
                count = 0
                for sub_entry in sub:
                    if sub_entry.name.startswith("."):
                        continue
                    lines.append(f"    {sub_entry.name}{'/' if sub_entry.is_dir() else ''}")
                    count += 1
                    if count >= 8:
                        lines.append("    ...")
                        break
            except OSError:
                pass
        else:
            lines.append(f"  {entry.name}")

    return "\n".join(lines)


def extract_context(root: Path, result: InfoResult) -> ProjectContext:
    """
    Build a ProjectContext from a root path and the InfoResult from scan().

    Args:
        root:   the directory that was scanned.
        result: the InfoResult returned by scan(root).
    Returns:
        a ProjectContext ready to be passed to the prompt builder.
    """
    # ── project type ────────────────────────────────────────────────
    project_type = result.heuristics.project_type or "Unknown"

    # ── primary language ────────────────────────────────────────────
    if result.languages:
        primary_language = _EXTENSION_TO_LANGUAGE.get(
            result.languages[0].extension, result.languages[0].extension
        )
    else:
        primary_language = "Unknown"

    # ── README ──────────────────────────────────────────────────────
    readme: str | None = None
    for name in _README_NAMES:
        candidate = root / name
        if candidate.is_file():
            readme = _read_truncated(candidate, _README_MAX_CHARS)
            break

    # ── tree summary ────────────────────────────────────────────────
    tree_summary = _build_tree_summary(root, result)

    # ── key file snippets ───────────────────────────────────────────
    snippets: list[tuple[str, str]] = []

    # Entry point files (root-level only, already detected by scanner)
    for ep in result.heuristics.entry_points[:3]:
        path = root / ep
        if path.is_file():
            content = _read_lines(path, _SNIPPET_MAX_LINES)
            if content.strip():
                snippets.append((ep, content))

    # Dependency manifest (gives the LLM package name + deps context)
    dep = result.heuristics.dependency_file
    if dep:
        dep_path = root / dep
        if dep_path.is_file():
            content = _read_lines(dep_path, _MANIFEST_MAX_LINES)
            if content.strip():
                snippets.append((dep, content))

    return ProjectContext(
        project_type=project_type,
        primary_language=primary_language,
        dependency_file=result.heuristics.dependency_file,
        readme=readme,
        tree_summary=tree_summary,
        snippets=snippets,
    )