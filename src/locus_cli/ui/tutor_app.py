"""
Textual TUI for `locus tutor`.

Side-by-side split: code viewer (left) + explanation panel (right).
Keyboard: j/k/up/down navigate, Enter/Space reveal, q quit.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.message import Message
from textual.containers import Horizontal
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

    #code-panel {
        width: 1fr;
        height: 1fr;
        border-right: solid $primary-darken-2;
        overflow-y: auto;
        padding: 0 1;
    }

    #explanation-panel {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
        color: $text;
    }

    .line-normal {
        color: $text-muted;
    }

    .line-highlight {
        background: $primary-darken-3;
        color: $text;
    }
    """

    BINDINGS = [
        ("j,down", "move_down", "Down"),
        ("k,up", "move_up", "Up"),
        ("enter,space", "reveal", "Reveal"),
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

    def compose(self) -> ComposeResult:
        with Horizontal(id="split"):
            yield Static(id="code-panel")
            yield Static(id="explanation-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._session = TutorSession(
            file_path=self._file_path,
            model_path=self._model_path,
            n_gpu_layers=self._n_gpu_layers,
            on_summary_ready=self._notify_summary_ready,
        )
        self._render_code()
        self._set_explanation("Analyzing file...")

    def _notify_summary_ready(self) -> None:
        """Callback for TutorSession — called from Worker A's thread."""
        self.call_from_thread(self.post_message, SummaryReady())

    # ------------------------------------------------------------------ #
    # Rendering helpers
    # ------------------------------------------------------------------ #

    def _render_code(self) -> None:
        """Re-render the code panel with the current line highlighted."""
        from rich.markup import escape

        assert self._session is not None
        lines = self._session.lines
        parts: list[str] = []
        for i, line in enumerate(lines, start=1):
            num = f"{i:>4}  "
            text = escape(line.rstrip("\n"))
            if i == self._cursor:
                parts.append(f"[reverse]\u25b6 {num}{text}[/reverse]")
            else:
                parts.append(f"[dim]  {num}[/dim]{text}")
        code_widget = self.query_one("#code-panel", Static)
        code_widget.update("\n".join(parts))

    def _set_explanation(self, text: str) -> None:
        self.query_one("#explanation-panel", Static).update(text)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def action_move_down(self) -> None:
        assert self._session is not None
        if self._cursor < len(self._session.lines):
            self._cursor += 1
            self._session.set_cursor(self._cursor)
            self._render_code()
            self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")

    def action_move_up(self) -> None:
        if self._cursor > 1:
            self._cursor -= 1
            if self._session:
                self._session.set_cursor(self._cursor)
            self._render_code()
            self._set_explanation("Press [bold]Enter[/bold] or [bold]Space[/bold] to explain this line.")

    def action_reveal(self) -> None:
        assert self._session is not None
        if not self._session._summary_ready.is_set():
            return  # still analyzing -- reveal is disabled
        cached = self._session.get_explanation(self._cursor)
        if cached is not None:
            self._set_explanation(cached)
        else:
            self._set_explanation("[dim]Generating...[/dim]")
            self._fetch_explanation(self._cursor)

    async def action_quit(self) -> None:
        self.exit()

    @work(thread=True)
    def _fetch_explanation(self, line_num: int) -> None:
        """Generate explanation on demand (runs in a thread)."""
        assert self._session is not None
        explanation = self._session.request_explanation(line_num)
        self.call_from_thread(self._set_explanation, explanation)

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #

    def on_summary_ready(self, _: SummaryReady) -> None:
        self._set_explanation(
            "Press [bold]Enter[/bold] or [bold]Space[/bold] to explain the current line."
        )
