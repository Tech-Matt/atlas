# This files needs to take a folder address like 'src' or '.' and return a Tree
# object which the UI can then render

# Global imports
from collections.abc import Callable
from pathlib import Path
import os
from rich.tree import Tree
from rich.filesize import decimal
from rich.markup import escape

# Local imports
from ..ui.console import console, supports_unicode, supports_nerd_fonts

# Maps file extension → Nerd Font DEV icon.
# Fallback for unrecognised extensions is "\ue5ff" (folder/file generic), or ">" on non-nerdfont terminals.
_NERD_ICONS: dict[str, str] = {
    # Python
    ".py": "\ue73c", ".pyw": "\ue73c", ".pyi": "\ue73c",
    # JavaScript / TypeScript
    ".js": "\ue781", ".mjs": "\ue781", ".cjs": "\ue781", ".jsx": "\ue781",
    ".ts": "\ue628", ".tsx": "\ue628",
    # Systems
    ".rs": "\ue7a8",
    ".go": "\ue627",
    ".c": "\ue61e", ".h": "\ue64b", ".cpp": "\ue61d", ".cc": "\ue61d", ".cxx": "\ue61d", ".hpp": "\ue64b",
    ".zig": "\ue209",
    # JVM
    ".java": "\ue256", ".kt": "\ue634", ".kts": "\ue634", ".scala": "\ue737",
    # Scripting
    ".rb": "\ue21e",
    ".lua": "\ue620",
    ".sh": "\ue795", ".bash": "\ue795", ".zsh": "\ue795", ".fish": "\ue795",
    # Web / styles
    ".html": "\ue736", ".htm": "\ue736",
    ".css": "\ue749", ".scss": "\ue749", ".sass": "\ue749", ".less": "\ue749",
    ".svelte": "\ue28d", ".vue": "\ue2a1",
    # Data / config
    ".json": "\ue60b", ".yaml": "\ue6a8", ".yml": "\ue6a8", ".toml": "\ue6b2", ".xml": "\ue7c3",
    ".env": "\uf023",
    ".lock": "\uf023",
    # Docs
    ".md": "\ue609", ".mdx": "\ue609", ".txt": "\uf15c", ".rst": "\uf15c",
    # Data science
    ".ipynb": "\ue606",
    ".r": "\ue6a8", ".jl": "\ue624",
    # Mobile
    ".swift": "\ue755",
    ".dart": "\ue2af",
    # Database
    ".sql": "\uf1c6",
    # Archives
    ".zip": "\uf1c6", ".tar": "\uf1c6", ".gz": "\uf1c6", ".rar": "\uf1c6", ".7z": "\uf1c6",
    # Media
    ".png": "\uf1c5", ".jpg": "\uf1c5", ".jpeg": "\uf1c5", ".gif": "\uf1c5",
    ".svg": "\uf1c5", ".webp": "\uf1c5",
    ".mp4": "\uf03d", ".mov": "\uf03d", ".avi": "\uf03d",
    ".mp3": "\uf001", ".wav": "\uf001", ".flac": "\uf001",
    # Documents
    ".pdf": "\uf1c1",
}

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
        gitignore_patterns = self._read_gitignore(root_dir)
        if ignore is not None:
            self.effective_ignore = self.IGNORE_FOLDERS | set(ignore) | gitignore_patterns
        else:
            self.effective_ignore = self.IGNORE_FOLDERS | gitignore_patterns

    @staticmethod
    def _read_gitignore(root: Path | str) -> set[str]:
        gitignore = Path(root) / ".gitignore"
        if not gitignore.is_file():
            return set()
        patterns: set[str] = set()
        for line in gitignore.read_text(errors="replace").splitlines():
            line = line.strip().lstrip("/")
            if line and not line.startswith("#") and not line.startswith("!"):
                patterns.add(line.rstrip("/"))
        return patterns

    def generate(self, on_progress: Callable[[], None] | None = None) -> Tree:
        """
        Starting from the root folder, it creates the tree and then returns it.

        on_progress: optional callback invoked after each directory is processed.
        """
        root_name = Path(self.root_dir).resolve().name
        tree = Tree(f"[bold blue]{root_name}[/]")
        self._walk(self.root_dir, tree, current_depth=0, on_progress=on_progress)
        return tree

    # The walk is based on a DFS Search (Depth first search)
    def _walk(self, directory, tree_node, current_depth, on_progress: Callable[[], None] | None = None) -> None:
        """
        It looks at 'directory' and adds items to 'tree_node'.
        It calls itself if it finds a subfolder.
        """
        try:
            # os.scandir() returns DirEntry objects whose is_dir() / is_file() /
            # is_symlink() use the cached d_type from readdir() — no extra syscall.
            entries = sorted(
                os.scandir(directory),
                key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower())
            )
        except PermissionError:
            tree_node.add("[red]Access Denied[/]")
            return

        directories: list[os.DirEntry[str]] = []
        files: list[os.DirEntry[str]] = []

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.name in self.effective_ignore:
                continue
            if entry.is_dir(follow_symlinks=False):
                directories.append(entry)
            elif entry.is_file(follow_symlinks=False):
                files.append(entry)

        for entry in directories:
            folder_icon = "\uf07b " if supports_nerd_fonts() else ""
            branch = tree_node.add(f"{folder_icon}[bold green]{escape(entry.name)}[/]")
            if current_depth < self.max_depth - 1:
                self._walk(entry.path, branch, current_depth + 1, on_progress)

        files_shown = 0
        for entry in files:
            if files_shown >= self.max_files:
                break
            try:
                file_size = decimal(entry.stat().st_size)
            except OSError:
                file_size = "?"
            if supports_nerd_fonts():
                ext = Path(entry.name).suffix.lower()
                icon = _NERD_ICONS.get(ext, "\uf15b") # default file icon
            else:
                icon = "" 
            
            # If icon is empty, we just don't add the space before it
            prefix = f"{icon} " if icon else ""
            tree_node.add(f"{prefix}{escape(entry.name)} ([dim]{file_size}[/])")
            files_shown += 1

        remaining_files = len(files) - files_shown
        if remaining_files > 0:
            tree_node.add(
                f"[dim italic]... {remaining_files} more file{'s' if remaining_files > 1 else ''}[/]"
            )

        if on_progress:
            on_progress()

# [REMOVE LATER] Just use this as temporary quick tests
if __name__ == "__main__":
    # Debug testing with console.print()
    root_folder = Path("~/LinuxSource/.").expanduser()
    map = LocusMap(root_folder, 3)
    tree = map.generate()
    console.print(tree)