import pytest
from pathlib import Path
from locus_cli.core.scanner import scan, InfoResult, ProjectHeuristics


# ---------------------------------------------------------------------------
# Guard clause
# ---------------------------------------------------------------------------

def test_scan_raises_on_nonexistent_root(tmp_path: Path) -> None:
    """scan() must raise ValueError when root does not exist."""
    with pytest.raises(ValueError):
        scan(tmp_path / "does_not_exist")


def test_scan_raises_on_file_root(tmp_path: Path) -> None:
    """scan() must raise ValueError when root is a file, not a directory."""
    f = tmp_path / "file.py"
    f.write_text("x = 1")
    with pytest.raises(ValueError):
        scan(f)


# ---------------------------------------------------------------------------
# Stats — Section 1
# ---------------------------------------------------------------------------

def test_scan_empty_dir_returns_zeros(tmp_path: Path) -> None:
    """An empty directory should produce all-zero stats and empty heuristics."""
    result = scan(tmp_path)
    assert result.total_files == 0
    assert result.total_dirs == 0
    assert result.total_bytes == 0
    assert result.languages == []


def test_scan_counts_files(tmp_path: Path) -> None:
    """total_files should count every non-hidden, non-ignored file."""
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")
    (tmp_path / "c.txt").write_text("hello")
    result = scan(tmp_path)
    assert result.total_files == 3


def test_scan_counts_dirs(tmp_path: Path) -> None:
    """total_dirs should count every non-hidden, non-ignored subdirectory."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "nested").mkdir()
    result = scan(tmp_path)
    assert result.total_dirs == 2


def test_scan_counts_total_bytes(tmp_path: Path) -> None:
    """total_bytes should be the sum of file sizes."""
    (tmp_path / "a.txt").write_bytes(b"x" * 100)
    (tmp_path / "b.txt").write_bytes(b"y" * 200)
    result = scan(tmp_path)
    assert result.total_bytes == 300


def test_scan_ignores_default_dirs(tmp_path: Path) -> None:
    """Files inside default-ignored dirs (e.g. node_modules) must not be counted."""
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("module.exports = {}")
    (tmp_path / "main.py").write_text("print('hi')")
    result = scan(tmp_path)
    assert result.total_files == 1  # only main.py


def test_scan_respects_custom_ignore(tmp_path: Path) -> None:
    """Files inside a user-supplied ignore dir must not be counted."""
    (tmp_path / "build_output").mkdir()
    (tmp_path / "build_output" / "artifact.bin").write_bytes(b"\x00" * 50)
    (tmp_path / "main.py").write_text("print('hi')")
    result = scan(tmp_path, ignore=["build_output"])
    assert result.total_files == 1


def test_scan_language_stats(tmp_path: Path) -> None:
    """Language stats should group files by extension."""
    (tmp_path / "a.py").write_text("x = 1")
    (tmp_path / "b.py").write_text("y = 2")
    (tmp_path / "c.js").write_text("const x = 1")
    result = scan(tmp_path)
    extensions = {ls.extension for ls in result.languages}
    assert ".py" in extensions
    assert ".js" in extensions
    py_stat = next(ls for ls in result.languages if ls.extension == ".py")
    assert py_stat.file_count == 2


def test_scan_returns_top_5_languages_only(tmp_path: Path) -> None:
    """When more than 5 extensions are present, only the top 5 should be returned."""
    for i, ext in enumerate([".py", ".js", ".ts", ".go", ".rs", ".c"]):
        for j in range(i + 1):  # give each ext a different count so ranking is deterministic
            (tmp_path / f"file_{ext[1:]}_{j}{ext}").write_text("x")
    result = scan(tmp_path)
    assert len(result.languages) <= 5


def test_scan_languages_sorted_by_file_count(tmp_path: Path) -> None:
    """Languages must be sorted descending by file_count."""
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("x")
    (tmp_path / "c.py").write_text("x")
    (tmp_path / "d.js").write_text("x")
    result = scan(tmp_path)
    counts = [ls.file_count for ls in result.languages]
    assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# Project Identity — Section 2
# ---------------------------------------------------------------------------

def test_scan_detects_project_type(tmp_path: Path) -> None:
    """A pyproject.toml at the root should set project_type to 'Python Package'."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    result = scan(tmp_path)
    assert result.heuristics.project_type == "Python Package"


def test_scan_detects_node_project_type(tmp_path: Path) -> None:
    """A package.json at the root should set project_type to 'Node.js Project'."""
    (tmp_path / "package.json").write_text('{"name": "test"}')
    result = scan(tmp_path)
    assert result.heuristics.project_type == "Node.js Project"


def test_scan_no_markers_gives_none_project_type(tmp_path: Path) -> None:
    """With no known marker files, project_type should remain None."""
    (tmp_path / "random.txt").write_text("hello")
    result = scan(tmp_path)
    assert result.heuristics.project_type is None


def test_scan_detects_entry_point(tmp_path: Path) -> None:
    """main.py at the root should appear in entry_points."""
    (tmp_path / "main.py").write_text("if __name__ == '__main__': pass")
    result = scan(tmp_path)
    assert "main.py" in result.heuristics.entry_points


def test_scan_does_not_detect_nested_entry_point(tmp_path: Path) -> None:
    """Entry points only count at the root level, not in subdirectories."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x = 1")
    result = scan(tmp_path)
    assert result.heuristics.entry_points == []


def test_scan_detects_test_dir(tmp_path: Path) -> None:
    """A 'tests' directory at the root should appear in test_dirs."""
    (tmp_path / "tests").mkdir()
    result = scan(tmp_path)
    assert "tests" in result.heuristics.test_dirs


def test_scan_detects_config_file(tmp_path: Path) -> None:
    """A known config file (e.g. Dockerfile) should appear in config_files."""
    (tmp_path / "Dockerfile").write_text("FROM python:3.12")
    result = scan(tmp_path)
    assert "Dockerfile" in result.heuristics.config_files


def test_scan_detects_github_actions_dir(tmp_path: Path) -> None:
    """The .github directory should appear in config_files when present."""
    (tmp_path / ".github").mkdir()
    result = scan(tmp_path)
    assert ".github" in result.heuristics.config_files


def test_scan_detects_dependency_file(tmp_path: Path) -> None:
    """The dependency manifest (e.g. pyproject.toml) should be recorded."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    result = scan(tmp_path)
    assert result.heuristics.dependency_file == "pyproject.toml"


def test_scan_no_dependency_file_gives_none(tmp_path: Path) -> None:
    """With no known dependency manifest, dependency_file should be None."""
    (tmp_path / "main.py").write_text("x = 1")
    result = scan(tmp_path)
    assert result.heuristics.dependency_file is None


# ---------------------------------------------------------------------------
# .gitignore support
# ---------------------------------------------------------------------------

def test_scan_respects_gitignore(tmp_path: Path) -> None:
    """Folders listed in .gitignore at the root should be excluded from scan."""
    (tmp_path / ".gitignore").write_text("secret_dir\n")
    (tmp_path / "secret_dir").mkdir()
    (tmp_path / "secret_dir" / "private.py").write_text("x = 1")
    (tmp_path / "main.py").write_text("x = 1")
    result = scan(tmp_path)
    assert result.total_files == 1  # only main.py, not private.py


def test_scan_gitignore_missing_is_fine(tmp_path: Path) -> None:
    """If no .gitignore exists, scan() must not crash."""
    (tmp_path / "main.py").write_text("x = 1")
    result = scan(tmp_path)
    assert result.total_files == 1


def test_scan_gitignore_ignores_comments_and_blanks(tmp_path: Path) -> None:
    """Comment lines and blank lines in .gitignore must not be treated as patterns."""
    (tmp_path / ".gitignore").write_text("# this is a comment\n\ndist\n")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "out.js").write_text("x")
    (tmp_path / "main.py").write_text("x = 1")
    result = scan(tmp_path)
    assert result.total_files == 1


# ---------------------------------------------------------------------------
# End-to-end CLI wiring
# ---------------------------------------------------------------------------

def test_full_cli_wiring_info_returns_zero(tmp_path: Path) -> None:
    """
    End-to-end: main(["info", <path>]) must return exit code 0.
    Tests the full argparse → cmd_info → scan() stack.
    """
    from locus_cli.main import main
    result = main(["info", str(tmp_path)])
    assert result == 0
