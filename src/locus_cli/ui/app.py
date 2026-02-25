# This file will use the Textual library to create a UI

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import ScrollableContainer, VerticalScroll
from pathlib import Path

from core.map import LocusMap

class LocusApp(App):
    """
    The Textual UI for locus
    """
    def __init__(self, root_dir, max_depth):
        # Let's call the textual.App constructor first (necessary)
        super().__init__()
        self.root_dir = root_dir
        self.max_depth = max_depth # Maximum depth of subfolders

    # Textual uses CSS for the UI
    CSS_PATH = "style.tcss"

    # Bindings: allow user to press keys to do things
    BINDINGS = [
        ("q", "quit", "Quit Locus"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("j", "scroll_down", "Scroll Down"),
        ("k", "scroll_up", "Scroll Up")
    ]

    def compose(self) -> ComposeResult:
        """
        Create child widgets for the APP
        """
        yield Header()
        yield VerticalScroll(Static(id="map-view"), id="main-scroll")
        yield Footer() 


    def on_mount(self) -> None:
        """
        This method runs exactly once, right after the app is
        built and rendered. This is where data is fetched and
        the UI updated
        """
        locus_map = LocusMap(self.root_dir, self.max_depth)
        tree = locus_map.generate()
        self.query_one("#map-view", Static).update(tree)
        pass

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )
    
    def action_scroll_down(self) -> None:
        scroll_view = self.query_one("#main-scroll", VerticalScroll)
        scroll_view.scroll_down()

    def action_scroll_up(self) -> None:
        scroll_view = self.query_one("#main-scroll", VerticalScroll)
        scroll_view.scroll_up()

    def action_quit(self) -> None:
        self.exit()

# [REMOVE LATER] For testing the UI directly
if __name__ == "__main__":
    app = LocusApp(Path("~/LinuxSource/linux/").expanduser(), 3)
    app.run()