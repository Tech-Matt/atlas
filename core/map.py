# This files needs to take a folder address like 'src' or '.' and return a Tree
# object which the UI can then render

import os
from pathlib import Path
from rich.tree import Tree
from rich.text import Text
from rich.filesize import decimal
from rich.markup import escape
from ui.console import console

class AtlasMap:
    # Default list of folders to ignore
    IGNORE_FOLDERS = {
        "__pycache__", 
        "node_modules", 
        "venv", 
        "myEnv",
        ".git", 
        ".idea", 
        ".vscode",
        "dist",
        "build",
        "target", # Rust/Java
        "bin",    # C#
        "obj",    # C#
        "vendor"  # PHP/Go
    }

    # The constructor gets called on the root folder of interest
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def generate(self):
        """
        Starting from the root folder, it creates the tree and then returns it
        """
        # Get the folder name
        # resolve() makes the Path absolute, resolving any symlink
        # .name returns the last part, like "setup.py"
        root_name = Path(self.root_dir).resolve().name

        # Create the visual Root Node
        tree = Tree(f"📂 [bold blue]{root_name}[/]")

        # Start walking in a recursive fashion
        self._walk(self.root_dir, tree)

        return tree

    def _walk(self, directory, tree_node):
        """
        It looks at 'directory' and adds items to 'tree_node'.
        It calls itself if it finds a subfolder
        """
        # Get all the items in the directory
        try:
            # Sorting works in this way:
            # - folders are showed first, then files. If same type, then order
            # - by name.
            paths = sorted(
                Path(directory).iterdir(), # This is a list of PosixPathor WinwdowsPath
                key=lambda p: (not p.is_dir(), p.name.lower())
            )

        except PermissionError:
            # Handle folders we can't open
            tree_node.add("[red]🚫 Access Denied[/]")
            return
        
        for path in paths:
            # Filter: skip hidden files or folders
            if path.name.startswith("."):
                continue
            # Filter: skip common dep/cache folders
            if path.name in self.IGNORE_FOLDERS: 
                continue


            # Handle directories (recursion)
            if path.is_dir():
                # Create a new branch for this folder
                # escape() here escapes the folder name to delete possible rich tags
                branch = tree_node.add(f"[bold green]📁 {escape(path.name)}[/]")
                # Recursion, dive into the folder
                self._walk(path, branch)
            
            # Handle files
            else:
                # Calculate size for display
                file_size = decimal(path.stat().st_size)
                # Add simple icons based on extension
                icon = "🐍" if path.suffix == ".py" else "📄"
                # Add the leaf node
                tree_node.add(
                    f"{icon} {escape(path.name)} ([dim]{file_size}[/])"
                )

# [REMOVE LATER] Just use this as temporary quick tests
if __name__ == "__main__":
    # Debug testing with console.print()
    root_folder = Path("~/LinuxSource/.").expanduser()
    map = AtlasMap(root_folder)
    tree = map.generate()
    console.print(tree)

