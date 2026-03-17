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
from ..ui.console import console, supports_unicode

# Maps file extension → emoji icon.
# Fallback for unrecognised extensions is "📄", or ">" on non-unicode terminals.
_EMOJI_ICONS: dict[str, str] = {
    # Python
    ".py": "🐍", ".pyw": "🐍", ".pyi": "🐍",
    # JavaScript / TypeScript
    ".js": "⚡", ".mjs": "⚡", ".cjs": "⚡", ".jsx": "⚡",
    ".ts": "⚡", ".tsx": "⚡",
    # Systems
    ".rs": "🦀",
    ".go": "🐹",
    ".c": "🔧", ".h": "🔧", ".cpp": "🔧", ".cc": "🔧", ".cxx": "🔧", ".hpp": "🔧",
    ".zig": "⚡",
    # JVM
    ".java": "☕", ".kt": "☕", ".kts": "☕", ".scala": "☕",
    # Scripting
    ".rb": "💎",
    ".lua": "🌙",
    ".sh": "💻", ".bash": "💻", ".zsh": "💻", ".fish": "💻",
    # Web / styles
    ".html": "🌐", ".htm": "🌐",
    ".css": "🎨", ".scss": "🎨", ".sass": "🎨", ".less": "🎨",
    ".svelte": "🌐", ".vue": "🌐",
    # Data / config
    ".json": "📋", ".yaml": "📋", ".yml": "📋", ".toml": "📋", ".xml": "📋",
    ".env": "🔑",
    ".lock": "🔒",
    # Docs
    ".md": "📝", ".mdx": "📝", ".txt": "📝", ".rst": "📝",
    # Data science
    ".ipynb": "📓",
    ".r": "📊", ".jl": "📊",
    # Mobile
    ".swift": "🍎",
    ".dart": "🎯",
    # Database
    ".sql": "🗄",
    # Archives
    ".zip": "📦", ".tar": "📦", ".gz": "📦", ".rar": "📦", ".7z": "📦",
    # Media
    ".png": "🖼", ".jpg": "🖼", ".jpeg": "🖼", ".gif": "🖼",
    ".svg": "🖼", ".webp": "🖼",
    ".mp4": "🎬", ".mov": "🎬", ".avi": "🎬",
    ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵",
    # Documents
    ".pdf": "📕",
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

    def generate(self, on_progress: Callable[[Tree], None] | None = None) -> Tree:
        """
        Starting from the root folder, it creates the tree and then returns it.

        on_progress: optional callback invoked after each directory is processed,
                     receiving the partial root Tree so far. Used by cmd_tree to
                     drive a Live streaming display.
        """
        root_name = Path(self.root_dir).resolve().name
        tree = Tree(f"[bold blue]{root_name}[/]")
        _notify: Callable[[], None] | None = (lambda: on_progress(tree)) if on_progress else None
        self._walk(self.root_dir, tree, current_depth=0, on_progress=_notify)
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
            branch = tree_node.add(f"[bold green]{escape(entry.name)}[/]")
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
            if supports_unicode():
                ext = Path(entry.name).suffix.lower()
                icon = _EMOJI_ICONS.get(ext, "📄")
            else:
                icon = ">"
            tree_node.add(f"{icon} {escape(entry.name)} ([dim]{file_size}[/])")
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