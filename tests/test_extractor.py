import pytest
from pathlib import Path
from locus_cli.core.scanner import scan
from locus_cli.core.extractor import extract_context, ProjectContext, _README_MAX_CHARS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path) -> Path:
    """Create a minimal Python project structure for testing."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    (tmp_path / "README.md").write_text("# Test Project\nThis does something cool.\n")
    (tmp_path / "main.py").write_text("def main():\n    pass\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core.py").write_text("# core logic\n")
    (tmp_path / "tests").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# ProjectContext fields
# ---------------------------------------------------------------------------

def test_extract_context_returns_project_context(tmp_path: Path) -> None:
    """extract_context() must return a ProjectContext instance."""
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert isinstance(ctx, ProjectContext)


def test_extract_context_project_type(tmp_path: Path) -> None:
    """project_type should reflect the marker file detected by scan()."""
    _make_project(tmp_path)
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert ctx.project_type == "Python Package"


def test_extract_context_primary_language(tmp_path: Path) -> None:
    """primary_language should be the top language by file count."""
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")
    (tmp_path / "c.js").write_text("const x = 1")
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert ctx.primary_language == "Python"


def test_extract_context_unknown_project_type_on_empty_dir(tmp_path: Path) -> None:
    """With no marker files, project_type should be 'Unknown'."""
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert ctx.project_type == "Unknown"


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

def test_extract_context_reads_readme(tmp_path: Path) -> None:
    """README.md content should be present in the context."""
    (tmp_path / "README.md").write_text("# Hello\nThis is a test project.\n")
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert ctx.readme is not None
    assert "Hello" in ctx.readme


def test_extract_context_no_readme_gives_none(tmp_path: Path) -> None:
    """When no README exists, ctx.readme should be None."""
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert ctx.readme is None


def test_extract_context_readme_is_truncated(tmp_path: Path) -> None:
    """README content longer than _README_MAX_CHARS must be truncated."""
    long_text = "x" * (_README_MAX_CHARS + 500)
    (tmp_path / "README.md").write_text(long_text)
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert ctx.readme is not None
    assert len(ctx.readme) < len(long_text)
    assert "truncated" in ctx.readme


# ---------------------------------------------------------------------------
# Tree summary
# ---------------------------------------------------------------------------

def test_extract_context_tree_summary_contains_root(tmp_path: Path) -> None:
    """tree_summary must start with the root directory name."""
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert tmp_path.name in ctx.tree_summary


def test_extract_context_tree_summary_contains_subdirs(tmp_path: Path) -> None:
    """Subdirectories should appear in the tree summary."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert "src" in ctx.tree_summary
    assert "tests" in ctx.tree_summary


# ---------------------------------------------------------------------------
# Snippets
# ---------------------------------------------------------------------------

def test_extract_context_includes_entry_point_snippet(tmp_path: Path) -> None:
    """Entry point files detected by scan() should appear in snippets."""
    (tmp_path / "main.py").write_text("def main():\n    print('hello')\n")
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    snippet_names = [name for name, _ in ctx.snippets]
    assert "main.py" in snippet_names


def test_extract_context_includes_dependency_manifest_snippet(tmp_path: Path) -> None:
    """The dependency manifest should appear in snippets."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    snippet_names = [name for name, _ in ctx.snippets]
    assert "pyproject.toml" in snippet_names


def test_extract_context_no_snippets_on_empty_dir(tmp_path: Path) -> None:
    """With no entry points or manifest, snippets should be empty."""
    result = scan(tmp_path)
    ctx = extract_context(tmp_path, result)
    assert ctx.snippets == []