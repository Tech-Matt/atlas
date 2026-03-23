"""Tests for core/tutor.py — no LLM required."""
from __future__ import annotations
import threading
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
    assert session.lines == ["def hello():", "    return 'hi'"]


# ---------------------------------------------------------------------------
# TutorSession — prompt builders
# ---------------------------------------------------------------------------

def _make_session(tmp_path: Path, content: str = "def foo():\n    return 1\n") -> object:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "sample.py"
    src.write_text(content)
    return TutorSession(src, n_gpu_layers=0, _skip_workers=True)


def test_build_summary_prompt_contains_filename(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    prompt = session.build_summary_prompt()
    assert "sample.py" in prompt


def test_build_summary_prompt_contains_file_content(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    prompt = session.build_summary_prompt()
    assert "def foo():" in prompt


def test_build_line_prompt_contains_line_content(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "This file defines foo."
    prompt = session.build_line_prompt(line_num=1)
    assert "def foo():" in prompt


def test_build_line_prompt_contains_summary(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "This file defines foo."
    prompt = session.build_line_prompt(line_num=1)
    assert "This file defines foo." in prompt


def test_build_line_prompt_contains_line_number(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"
    prompt = session.build_line_prompt(line_num=2)
    assert "line 2" in prompt


def test_build_line_prompt_marks_current_line(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"
    prompt = session.build_line_prompt(line_num=1)
    assert ">>>" in prompt


# ---------------------------------------------------------------------------
# TutorSession — line_cache interface
# ---------------------------------------------------------------------------

def test_get_explanation_returns_none_on_cache_miss(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    assert session.get_explanation(1) is None


def test_get_explanation_returns_cached_value(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.line_cache[1] = "This defines foo."
    assert session.get_explanation(1) == "This defines foo."


def test_request_explanation_uses_injected_llm(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"

    def fake_llm(prompt: str) -> str:
        return "Fake explanation."

    result = session.request_explanation(1, _llm_fn=fake_llm)
    assert result == "Fake explanation."


def test_request_explanation_caches_result(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"

    session.request_explanation(1, _llm_fn=lambda p: "cached!")
    assert session.get_explanation(1) == "cached!"


def test_request_explanation_does_not_regenerate_cached(tmp_path: Path) -> None:
    session = _make_session(tmp_path)
    session.file_summary = "summary"
    session.line_cache[1] = "already cached"

    call_count = {"n": 0}
    def counting_llm(prompt: str) -> str:
        call_count["n"] += 1
        return "new value"

    result = session.request_explanation(1, _llm_fn=counting_llm)
    assert result == "already cached"
    assert call_count["n"] == 0


# ---------------------------------------------------------------------------
# TutorSession — Worker A (file summary)
# ---------------------------------------------------------------------------

def test_on_summary_ready_fires_after_summary_set(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "a.py"
    src.write_text("x = 1\n")

    fired = threading.Event()

    def fake_llm(prompt: str) -> str:
        return "A summary."

    session = TutorSession(
        src,
        n_gpu_layers=0,
        _skip_workers=True,
    )
    session._run_worker_a(llm_fn=fake_llm, on_done=lambda: fired.set())
    assert fired.wait(timeout=2), "on_summary_ready was never called"
    assert session.file_summary == "A summary."


def test_summary_ready_event_is_set_after_worker_a(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "a.py"
    src.write_text("x = 1\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session._run_worker_a(llm_fn=lambda p: "summary", on_done=lambda: None)
    assert session._summary_ready.is_set()
