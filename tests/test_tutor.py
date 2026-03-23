"""Tests for core/tutor.py — no LLM required."""
from __future__ import annotations
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# TutorSession — file validation
# ---------------------------------------------------------------------------

def test_tutor_session_raises_on_missing_file(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    with pytest.raises(ValueError, match="does not exist"):
        TutorSession(tmp_path / "missing.py", n_gpu_layers=0)


def test_tutor_session_raises_on_directory(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    with pytest.raises(ValueError, match="not a file"):
        TutorSession(tmp_path, n_gpu_layers=0)


def test_tutor_session_raises_on_binary_file(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    with pytest.raises(ValueError, match="binary"):
        TutorSession(binary, n_gpu_layers=0)


def test_tutor_session_raises_when_file_too_long(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    big = tmp_path / "big.py"
    big.write_text("\n".join(f"x = {i}" for i in range(501)))
    with pytest.raises(ValueError, match="501 lines"):
        TutorSession(big, n_gpu_layers=0)


def test_tutor_session_raises_when_file_too_large(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    big = tmp_path / "big.py"
    # Write just over 20 KB
    big.write_bytes(b"x = 1\n" * 3500)
    with pytest.raises(ValueError, match="20 KB"):
        TutorSession(big, n_gpu_layers=0)


def test_tutor_session_accepts_valid_python_file(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "hello.py"
    src.write_text("def hello():\n    return 'hi'\n")
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    assert session.lines == ["def hello():", "    return 'hi'", ""]
