"""
Textual TUI for `locus tutor`.

Side-by-side split: code viewer (left) + explanation panel (right).
Keyboard: j/k/up/down navigate, Enter/Space reveal, q quit.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.message import Message
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Footer, Static
from textual import work

from ..core.tutor import TutorSession


class SummaryReady(Message):
    """Posted by TutorSession.on_summary_ready callback -> TutorApp."""


class TutorApp(App[None]):
    """Interactive line-by-line code tutor."""

    CSS = """
    TutorApp {
        background: $surface;
    }

    #split {
        height: 1fr;
    }

    #code-container {
        width: 1fr;
        height: 1fr;
        border-right: solid $primary-darken-2;
    }

    #code-panel {
        width: 100%;
        height: auto;
        padding: 0 1;
    }

    #explanation-container {
        width: 1fr;
        height: 1fr;
    }

    #explanation-panel {
        width: 100%;
        height: auto;
        padding: 1 2;
        color: $text;
    }
    """

    BINDINGS = [
        ("j,down", "move_down", "Down"),
        ("k,up", "move_up", "Up"),
        ("enter,space", "reveal", "Explain"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        file_path: Path,
        model_path: Path,
        n_gpu_layers: int,
    ) -> None:
        super().__init__()
        self._file_path = file_path
        self._model_path = model_path
        self._n_gpu_layers = n_gpu_layers
        self._cursor = 1  # 1-indexed
        self._session: TutorSession | None = None
        self._loading_timer = None
        self._loading_dots = 0
        self._loading_msg = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="split"):
            with VerticalScroll(id="code-container"):
                yield Static(id="code-panel")
            with VerticalScroll(id="explanation-container"):
                yield Static(id="explanation-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._render_code()
        self._start_loading_animation("Loading AI backend and analyzing file")
        
        # Start session after a small delay to ensure UI mounts first
        self.set_timer(0.1, self._start_session)

    def _start_session(self) -> None:
        self._session = TutorSession(
            file_path=self._file_path,
            model_path=self._model_path,
            n_gpu_layers=self._n_gpu_layers,
            on_summary_ready=self._notify_summary_ready,
        )
        self._render_code()

    def _notify_summary_ready(self) -> None:
        self.call_from_thread(self.post_message, SummaryReady())

    # ------------------------------------------------------------------ #
    # Rendering helpers
    # ------------------------------------------------------------------ #

    def _render_code(self) -> None:
        """Re-render the code panel with the current line highlighted."""
        from rich.syntax import Syntax

        code_widget = self.query_one("#code-panel", Static)

        if self._session is None:
            try:
                # Pre-session snippet
                content = self._file_path.read_text(encoding="utf-8")
                lines = content.splitlines()[:50]
                code_text = "\n".join(lines)
            except Exception:
                code_text = "Loading..."
        else:
            code_text = "\n".join(self._session.lines)

        ext = self._file_path.suffix.lstrip(".").lower()
        if not ext:
            ext = "text"
            
        highlight_set = {self._cursor} if self._session else set()

        syntax = Syntax(
            code_text,
            lexer=ext,
            theme="monokai",
            line_numbers=True,
            highlight_lines=highlight_set,
            word_wrap=False,
            indent_guides=True,
            background_color="default",
        )
        
        code_widget.update(syntax)
        
        if self._session is not None:
            container = self.query_one("#code-container", VerticalScroll)
            h = container.size.height
            if h > 0:
                cursor_y = self._cursor - 1
                current_top = container.scroll_y
                current_bottom = current_top + h
                
                # Keep cursor in visible area
                padding = 3
                if cursor_y < current_top + padding:
                    container.scroll_to(y=max(0, cursor_y - padding), animate=False)
                elif cursor_y >= current_bottom - padding:
                    container.scroll_to(y=cursor_y - h + padding + 1, animate=False)

    def _set_explanation(self, text: str) -> None:
        self.query_one("#explanation-panel", Static).update(text)

    def _start_loading_animation(self, msg: str) -> None:
        self._stop_loading_animation()
        self._loading_msg = msg
        self._loading_dots = 0
        def _update() -> None:
            dots = "." * (self._loading_dots % 4)
            self._loading_dots += 1
            # Using simple dim text to prevent "flashing" while updating
            self._set_explanation(f"[dim]{self._loading_msg}{dots}[/dim]")
        _update()
        self._loading_timer = self.set_interval(0.4, _update)

    def _stop_loading_animation(self) -> None:
        if self._loading_timer is not None:
            self._loading_timer.stop()
            self._loading_timer = None

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def action_move_down(self) -> None:
        if self._session and self._cursor < len(self._session.lines):
            self._cursor += 1
            self._session.set_cursor(self._cursor)
            self._render_code()
            cached = self._session.get_explanation(self._cursor)
            if cached is not None:
                self._stop_loading_animation()
                self._set_explanation(cached)
            else:
                self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")

    def action_move_up(self) -> None:
        if self._session and self._cursor > 1:
            self._cursor -= 1
            self._session.set_cursor(self._cursor)
            self._render_code()
            cached = self._session.get_explanation(self._cursor)
            if cached is not None:
                self._stop_loading_animation()
                self._set_explanation(cached)
            else:
                self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")

    def action_reveal(self) -> None:
        if self._session is None:
            return
            
        if not self._session._summary_ready.is_set():
            self._start_loading_animation("Reading entire file for overall analysis... please wait")
            return
            
        cached = self._session.get_explanation(self._cursor)
        if cached is not None:
            self._stop_loading_animation()
            self._set_explanation(cached)
        else:
            self._start_loading_animation("Analyzing context and generating insights")
            self._fetch_explanation(self._cursor)

    async def action_quit(self) -> None:
        self._stop_loading_animation()
        self.exit()

    @work(thread=True)
    def _fetch_explanation(self, line_num: int) -> None:
        assert self._session is not None
        first_token = True
        accumulated: list[str] = []

        def _on_token(token: str) -> None:
            nonlocal first_token
            should_stop = first_token
            first_token = False  # flip on worker thread, before dispatching
            accumulated.append(token)
            current_text = "".join(accumulated)

            def _update() -> None:
                if should_stop:
                    self._stop_loading_animation()
                self._set_explanation(current_text)

            self.call_from_thread(_update)

        def _on_done(full_text: str) -> None:
            # Stop animation in case stream_explanation returned from cache
            # (on_token never fired, so animation is still running)
            def _finish() -> None:
                self._stop_loading_animation()
                self._set_explanation(full_text)
            self.call_from_thread(_finish)

        self._session.stream_explanation(line_num, _on_token, _on_done)

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #

    def on_summary_ready(self, _: SummaryReady) -> None:
        self._stop_loading_animation()
        self._set_explanation(
            "Press [bold]Enter[/bold] or [bold]Space[/bold] to explain the current line."
        )
