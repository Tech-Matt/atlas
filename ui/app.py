# This file will use the Textual library to create a UI

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import ScrollableContainer

from core.map import AtlasMap

class AtlasApp(App):
    # CSS like syntax for styling
    CSS = """
    Screen {
        layout: vertical;
    }
    #tree-container {
        width: 100%;
        height: 1fr; /* Takes up the remaining space */
        padding: 1 2; /* 1 row top / bottom, 2 cols left/right */
    }    
    """

    # Bindings: allow user to press keys to do things
    BINDINGS = [
        ("q", "quit", "Quit Atlas")
    ]

    def compose(self) -> ComposeResult:
        """
        This method defines the layout of the App.
        """
        # TODO: Yield a header
        # TODO: Yield a Scrollable container
        # Inside the container, yield a Static() widget with
        # id="map-view". The static widget is where we inject
        # the Rich tree later

        # TODO: yield a Footer()
    
    def on_mount(self) -> None:
        """
        This method runs exactly once, right after the app is
        built and rendered. This is where data is fetched and
        the UI updated
        """
        # TODO: Instantiate AtlasMap pointing to "." (or any dir)
        # TODO: Call generate() to get the rich tree object
        # TODO: Query the UI for your map-view widget and update it with the tree
        # hint: self.query_one("#map-view", Static).update(your_tree)
        pass


# [REMOVE LATER] For testing the UI directly
if __name__ == "__main__":
    app = AtlasApp()
    app.run()