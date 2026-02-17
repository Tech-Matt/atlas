# This files needs to take a folder address like 'src' or '.' and return a Tree
# object which the UI can then render

import os
from pathlib import Path
from rich.tree import Tree
from rich.text import Text
from rich.filesize import decimal
from rich.markup import escape

class AtlasMap:
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def generate(self):
        """
        Creates the root of the tree and begin the recursive walk
        """
        # Get the folder name
        root_name = Path(self.root_dir).resolve().name

        # Create the visual Root Node
        tree = Tree(f"📂 [bold blue]{root_name}[/]")

        # Start walking in a recursive fashion
        self._walk(self.root_dir, tree)

    def _walk(self, directory, tree_node):
        """
        The recursive worker.
        It looks at 'directory' and adds items to 'tree_node'.
        It calls itself if it finds a subfolder
        """


