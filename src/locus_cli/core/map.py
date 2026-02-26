# This files needs to take a folder address like 'src' or '.' and return a Tree
# object which the UI can then render

# Global imports
from pathlib import Path
from rich.tree import Tree
from rich.filesize import decimal
from rich.markup import escape

# Local imports
from ..ui.console import console

class LocusMap:
    # Default list of folders to ignore. (This is a class variable, like a static variable in C)
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
    
    def __init__(self, root_dir, max_depth, max_files=10, ignore=None) -> None:
        """
        root_dir: Root directory of the desired codebase to be inspected
        max_depth: commands will go inside subfolder max_depth times
        max_files: max files to show in the UI for every folder
        ignore: Files or folders to be excluded from the search
        """
        self.root_dir = root_dir
        self.max_depth = max_depth
        self.max_files = max_files
        # Combine user excluded folders to default excluded folders
        if ignore is not None:
            self.effective_ignore = self.IGNORE_FOLDERS | set(ignore)
        else:
            self.effective_ignore = self.IGNORE_FOLDERS

    def generate(self) -> Tree:
        """
        Starting from the root folder, it creates the tree and then returns it
        """
        # Get the folder name
        # resolve() makes the Path absolute, resolving any symlink
        # .name returns the last part, like "setup.py"
        root_name = Path(self.root_dir).resolve().name

        # Create the visual Root Node
        tree = Tree(f"[bold blue]{root_name}[/]")

        # Start walking in a recursive fashion
        self._walk(self.root_dir, tree, current_depth=0)

        return tree

    # The walk is based on a DFS Search (Depth first search)
    def _walk(self, directory, tree_node, current_depth) -> None:
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
            tree_node.add("[red]Access Denied[/]")
            return
        
        # Separate directories and files for the heuristic
        directories = []
        files = []

        for path in paths:
            # Filter: skip hidden files or folders
            if path.name.startswith("."):
                continue
            # Filter: skip common dep/cache folders
            if path.name in self.effective_ignore: 
                continue

            if path.is_dir():
                directories.append(path)
            else:
                files.append(path)

        # Always show all directories (no limit)
        for path in directories:
            # Create a new branch for this folder
            # escape() here escapes the folder name to delete possible rich tags
            branch = tree_node.add(f"[bold green]{escape(path.name)}[/]")

            # Recursion, dive into the folder only if we haven't hit the depth limit
            if current_depth < self.max_depth - 1:
                self._walk(path, branch, current_depth + 1)
        
        # Limit the number of files shown
        files_shown = 0
        for path in files:
            if files_shown >= self.max_files:
                break
            
            # Calculate size for display
            file_size = decimal(path.stat().st_size)
            # Add simple icons based on extension
            icon = "🐍" if path.suffix == ".py" else "📄"
            # Add the leaf node
            tree_node.add(
                f"{icon} {escape(path.name)} ([dim]{file_size}[/])"
            )
            files_shown += 1
        
        # If there are more files than shown, add a summary message
        remaining_files = len(files) - files_shown
        if remaining_files > 0:
            tree_node.add(
                f"[dim italic]... {remaining_files} more file{'s' if remaining_files > 1 else ''}[/]"
            )

# [REMOVE LATER] Just use this as temporary quick tests
if __name__ == "__main__":
    # Debug testing with console.print()
    root_folder = Path("~/LinuxSource/.").expanduser()
    map = LocusMap(root_folder, 3)
    tree = map.generate()
    console.print(tree)