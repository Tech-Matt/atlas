"""Tests for core/inference.py — prompt builder only (no LLM required)."""
from __future__ import annotations
from pathlib import Path
import pytest

from locus_cli.core.extractor import ProjectContext


def _make_ctx(**overrides) -> ProjectContext:
    defaults = dict(
        project_type="Python Package",
        primary_language="Python",
        dependency_file="pyproject.toml",
        readme="# MyProject\nA sample project.",
        tree_summary="myproject/\n  src/\n    main.py\n  tests/",
        snippets=[("src/main.py", "def main():\n    pass\n")],
    )
    defaults.update(overrides)
    return ProjectContext(**defaults)


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_contains_project_type() -> None:
    from locus_cli.core.inference import build_prompt
    prompt = build_prompt(_make_ctx())
    assert "Python Package" in prompt


def test_build_prompt_contains_primary_language() -> None:
    from locus_cli.core.inference import build_prompt
    prompt = build_prompt(_make_ctx())
    assert "Python" in prompt


def test_build_prompt_contains_tree_summary() -> None:
    from locus_cli.core.inference import build_prompt
    prompt = build_prompt(_make_ctx())
    assert "myproject/" in prompt


def test_build_prompt_contains_readme() -> None:
    from locus_cli.core.inference import build_prompt
    prompt = build_prompt(_make_ctx())
    assert "# MyProject" in prompt


def test_build_prompt_no_readme_does_not_crash() -> None:
    from locus_cli.core.inference import build_prompt
    prompt = build_prompt(_make_ctx(readme=None))
    assert "Python Package" in prompt


def test_build_prompt_contains_snippets() -> None:
    from locus_cli.core.inference import build_prompt
    prompt = build_prompt(_make_ctx())
    assert "src/main.py" in prompt
    assert "def main():" in prompt


def test_build_prompt_no_dependency_file() -> None:
    from locus_cli.core.inference import build_prompt
    prompt = build_prompt(_make_ctx(dependency_file=None))
    assert "Python Package" in prompt


# ---------------------------------------------------------------------------
# Provisioner — get_model_path / is_model_cached
# ---------------------------------------------------------------------------

def test_get_model_path_returns_gguf_under_models_dir(tmp_path: Path) -> None:
    from locus_cli.core.provisioner import Provisioner
    p = Provisioner(locus_dir=tmp_path)
    model_path = p.get_model_path(tier=4)
    assert model_path.suffix == ".gguf"
    assert model_path.parent == p.models_dir


def test_is_model_cached_false_when_file_missing(tmp_path: Path) -> None:
    from locus_cli.core.provisioner import Provisioner
    p = Provisioner(locus_dir=tmp_path)
    assert p.is_model_cached(tier=4) is False


def test_is_model_cached_true_when_file_present(tmp_path: Path) -> None:
    from locus_cli.core.provisioner import Provisioner
    p = Provisioner(locus_dir=tmp_path)
    p.get_model_path(tier=4).touch()
    assert p.is_model_cached(tier=4) is True


def test_all_tiers_have_model_path(tmp_path: Path) -> None:
    from locus_cli.core.provisioner import Provisioner
    p = Provisioner(locus_dir=tmp_path)
    for tier in (1, 2, 3, 4):
        path = p.get_model_path(tier)
        assert path.name.endswith(".gguf")
