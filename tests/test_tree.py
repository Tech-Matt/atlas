import pytest
from pathlib import Path
from locus_cli.core.map import LocusMap


def test_tree_generates_without_crashing(tmp_path: Path) -> None:
    """
    Sanity check: LocusMap should return a Rich Tree object without raising
    any exceptions, even on a completely empty directory.
    """
    # Map on empty directory
    locus_map = LocusMap(tmp_path, max_depth=2, max_files=10, ignore=None)
    tree = locus_map.generate()

    assert tree is not None


def test_default_ignore_folders_are_excluded(tmp_path: Path) -> None:
    """
    Folders in IGNORE_FOLDERS (the class-level constant) should never
    appear in effective_ignore, regardless of what the user passes.
    """
    # Create real folder structure inside the controlled temp directory
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules").mkdir()  # In IGNORE_FOLDERS → must be ignored
    (tmp_path / ".git").mkdir()          # In IGNORE_FOLDERS → must be ignored

    locus_map = LocusMap(tmp_path, max_depth=2, max_files=10, ignore=None)

    assert "node_modules" in locus_map.effective_ignore
    assert ".git" in locus_map.effective_ignore
    # A normal folder should NOT be in the ignore set
    assert "src" not in locus_map.effective_ignore


def test_user_ignore_list_is_merged(tmp_path: Path) -> None:
    """
    Custom folders passed via the `ignore` parameter should be merged
    into effective_ignore on top of the defaults.
    """
    (tmp_path / "my_build_dir").mkdir()

    locus_map = LocusMap(tmp_path, max_depth=2, max_files=10, ignore=["my_build_dir"])

    # User-provided folder must be present
    assert "my_build_dir" in locus_map.effective_ignore
    # Default folders must still be present after the merge
    assert "node_modules" in locus_map.effective_ignore


def test_class_constant_is_not_mutated(tmp_path: Path) -> None:
    """
    Creating a LocusMap instance with custom ignore folders must NEVER
    modify the shared class-level IGNORE_FOLDERS constant.

    if IGNORE_FOLDERS were mutated, a second instance would inherit the
    first instance's custom ignore entries, which is incorrect.
    """
    original_defaults = LocusMap.IGNORE_FOLDERS.copy()

    # Create an instance with a custom ignore entry
    LocusMap(tmp_path, max_depth=2, max_files=10, ignore=["my_build_dir"])

    # The class-level constant must be identical to what it was before
    assert LocusMap.IGNORE_FOLDERS == original_defaults


def test_max_files_limit_is_respected(tmp_path: Path) -> None:
    """
    When a directory contains more files than max_files, LocusMap must
    not add more than max_files file nodes to the tree.
    """
    # Create 20 fake Python files in the temp directory
    for i in range(20):
        (tmp_path / f"file_{i}.py").write_text("# placeholder")

    locus_map = LocusMap(tmp_path, max_depth=1, max_files=5, ignore=None)
    tree = locus_map.generate()

    # tree.children is the list of Rich renderables added to the root node.
    # We exclude the "... N more files" truncation notice from the count.
    file_nodes = [c for c in tree.children if "more file" not in str(c.label)]
    assert len(file_nodes) <= 5


def test_hidden_files_are_excluded(tmp_path: Path) -> None:
    """
    Files and folders starting with '.' (dot-files) should never appear
    in the generated tree, as they are filtered in _walk.
    """
    (tmp_path / ".env").write_text("SECRET=123")
    (tmp_path / ".hidden_folder").mkdir()
    (tmp_path / "visible.py").write_text("# visible")

    locus_map = LocusMap(tmp_path, max_depth=2, max_files=10, ignore=None)
    tree = locus_map.generate()

    # Collect all node labels as strings for easy inspection
    labels = [str(c.label) for c in tree.children]

    assert not any(".env" in label for label in labels)
    assert not any(".hidden_folder" in label for label in labels)
    assert any("visible.py" in label for label in labels)


def test_full_cli_wiring_returns_zero(tmp_path: Path) -> None:
    """
    End-to-end integration test: calling main() with ["tree", <path>]
    should return exit code 0 (success).

    This test exercises the full stack: argparse → cmd_tree → LocusMap.
    If any part of the wiring is broken, this test will catch it.
    """
    from locus_cli.main import main

    # Pass the tmp_path as a string, exactly as the OS would pass it
    result = main(["tree", str(tmp_path)])
    assert result == 0