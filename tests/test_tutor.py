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


def test_tutor_session_raises_when_file_too_large(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    big = tmp_path / "big.py"
    # Write just over 500 KB
    big.write_bytes(b"x" * (500 * 1024 + 1))
    with pytest.raises(ValueError, match="500 KB"):
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


# ---------------------------------------------------------------------------
# TutorSession — Worker B (prefetch queue)
# ---------------------------------------------------------------------------

def test_worker_b_populates_cache(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "b.py"
    src.write_text("a = 1\nb = 2\nc = 3\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"
    session._cursor_line = 1

    session._run_worker_b(
        start_line=1,
        llm_fn=lambda p: "explanation",
        stop_event=threading.Event(),
    )

    # All three lines should be cached
    assert session.get_explanation(1) == "explanation"
    assert session.get_explanation(2) == "explanation"
    assert session.get_explanation(3) == "explanation"


def test_worker_b_skips_already_cached_lines(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "b.py"
    src.write_text("a = 1\nb = 2\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"
    session.line_cache[1] = "pre-cached"
    session._cursor_line = 1

    call_count = {"n": 0}
    def counting_llm(p: str) -> str:
        call_count["n"] += 1
        return "new"

    session._run_worker_b(
        start_line=1,
        llm_fn=counting_llm,
        stop_event=threading.Event(),
    )
    # Line 1 was already cached; only line 2 should trigger LLM
    assert call_count["n"] == 1
    assert session.get_explanation(1) == "pre-cached"


def test_worker_b_respects_stop_event(tmp_path: Path) -> None:
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "b.py"
    src.write_text("\n".join(f"x = {i}" for i in range(50)) + "\n")

    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"
    session._cursor_line = 1

    stop = threading.Event()
    stop.set()  # pre-set: worker should exit immediately

    session._run_worker_b(start_line=1, llm_fn=lambda p: "x", stop_event=stop)
    # Cache should be empty or at most 1 entry — worker exited early
    assert len(session.line_cache) <= 1


# ---------------------------------------------------------------------------
# cmd_tutor — CLI validation (no LLM, no TUI)
# ---------------------------------------------------------------------------

def test_tutor_cli_rejects_missing_file(tmp_path: Path) -> None:
    from locus_cli.main import main
    result = main(["tutor", str(tmp_path / "missing.py")])
    assert result != 0


def test_tutor_cli_rejects_binary_file(tmp_path: Path) -> None:
    from locus_cli.main import main
    binary = tmp_path / "img.png"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    result = main(["tutor", str(binary)])
    assert result != 0


def test_build_line_prompt_sliding_window(tmp_path: Path) -> None:
    """Prompt should contain only a window of lines, not the full file."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "big.py"
    # 200-line file: line N contains "LINE_N"
    src.write_text("\n".join(f"# LINE_{i}" for i in range(1, 201)))
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"

    prompt = session.build_line_prompt(line_num=100)

    # Should contain the window header
    assert "Lines 60" in prompt
    assert "140 of 200" in prompt
    # Should contain lines within the window
    assert "LINE_60" in prompt
    assert "LINE_140" in prompt
    # Should NOT contain lines outside the window
    assert "# LINE_1\n" not in prompt
    assert "LINE_200" not in prompt


def test_build_summary_prompt_large_file_uses_sampling(tmp_path: Path) -> None:
    """Summary prompt for large files should use head+middle+tail sampling."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "large.py"
    # 500-line file: each line is "# LINE_N"
    src.write_text("\n".join(f"# LINE_{i}" for i in range(1, 501)))
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)

    prompt = session.build_summary_prompt()

    # Should contain the omission marker
    assert "[..." in prompt
    # Should contain head lines
    assert "LINE_1" in prompt
    assert "LINE_300" in prompt
    # Should contain tail lines
    assert "LINE_500" in prompt
    # Should NOT contain all 500 lines verbatim
    assert prompt.count("LINE_") < 500


def test_build_summary_prompt_very_large_file_uses_three_sections(tmp_path: Path) -> None:
    """Files > ~700 lines should produce head + middle + tail with two omission markers."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "very_large.py"
    # 900-line file — forces mid_start > 300, activating the three-section path
    src.write_text("\n".join(f"# LINE_{i}" for i in range(1, 901)))
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)

    prompt = session.build_summary_prompt()

    # Two omission markers (before mid and before tail)
    assert prompt.count("[...") == 2
    # Head present
    assert "LINE_1" in prompt
    assert "LINE_300" in prompt
    # Middle present (centred around line 450); mid_start=400 → lines[400:500] → LINE_401-LINE_500
    assert "LINE_401" in prompt
    # Tail present
    assert "LINE_900" in prompt
    # Not all 900 lines
    assert prompt.count("LINE_") < 900


def test_stream_explanation_fires_tokens_and_done(tmp_path: Path) -> None:
    """stream_explanation calls on_token for each token and on_done with full text."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"

    tokens_received: list[str] = []
    done_text: list[str] = []

    def fake_stream(prompt: str, on_token_fn: object) -> str:
        for tok in ["Hello", " ", "world"]:
            on_token_fn(tok)  # type: ignore[operator]
        return "Hello world"

    session.stream_explanation(
        line_num=1,
        on_token=tokens_received.append,
        on_done=done_text.append,
        _stream_fn=fake_stream,
    )

    assert tokens_received == ["Hello", " ", "world"]
    assert done_text == ["Hello world"]
    assert session.get_explanation(1) == "Hello world"


def test_stream_explanation_caches_result(tmp_path: Path) -> None:
    """stream_explanation stores result in line_cache before calling on_done."""
    from locus_cli.core.tutor import TutorSession
    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    session = TutorSession(src, n_gpu_layers=0, _skip_workers=True)
    session.file_summary = "summary"

    session.stream_explanation(
        line_num=1,
        on_token=lambda t: None,
        on_done=lambda full: None,
        _stream_fn=lambda p, cb: (cb("ok"), "ok")[1],
    )

    assert session.get_explanation(1) == "ok"
