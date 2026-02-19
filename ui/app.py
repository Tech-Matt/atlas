# This file will use the Textual library to create a UI

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import ScrollableContainer, VerticalScroll
from pathlib import Path

from core.map import AtlasMap

class AtlasApp(App):
    """
    The Textual UI for atlas
    """
    def __init__(self, root_dir):
        # Let's call the textual.App constructor first (necessary)
        super().__init__()
        self.root_dir = root_dir

    # Textual uses CSS for the UI
    CSS_PATH = "style.tcss"

    # Bindings: allow user to press keys to do things
    BINDINGS = [
        ("q", "quit", "Quit Atlas"),
        ("d", "toggle_dark", "Toggle Dark Mode")
    ]

    def compose(self) -> ComposeResult:
        """
        Create child widgets for the APP
        """
        yield Header()
        yield VerticalScroll(Static(id="map-view"))
        yield Footer() 


    def on_mount(self) -> None:
        """
        This method runs exactly once, right after the app is
        built and rendered. This is where data is fetched and
        the UI updated
        """
        atlas_map = AtlasMap(self.root_dir)
        tree = atlas_map.generate()
        self.query_one("#map-view", Static).update(tree)
        pass

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_quit(self) -> None:
        pass

# [REMOVE LATER] For testing the UI directly
if __name__ == "__main__":
    app = AtlasApp(".")
    app.run()