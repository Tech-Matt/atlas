from pathlib import Path

from rich.console import Console, Group
from rich.columns import Columns
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.filesize import decimal

from ..core.scanner import InfoResult, LanguageStat
from ..core.scanner import _EXTENSION_TO_LANGUAGE
from ..ui.console import supports_unicode

_BAR_WIDTH = 22
# Bar colors fade with rank: brightest first
_BAR_COLORS = ["bright_green", "green", "green3", "dark_green", "grey50"]


def _human_size(total_bytes: int) -> str:
    return decimal(total_bytes)


def _language_label(ls: LanguageStat) -> str:
    return _EXTENSION_TO_LANGUAGE.get(ls.extension, ls.extension)


def _bar(file_count: int, max_count: int, rank: int) -> Text:
    filled = round((file_count / max_count) * _BAR_WIDTH) if max_count else 0
    color = _BAR_COLORS[min(rank, len(_BAR_COLORS) - 1)]
    char = "█" if supports_unicode() else "#"
    return Text(char * filled, style=color)


def _build_languages_panel(result: InfoResult) -> Panel:
    table = Table(box=None, show_header=False, padding=(0, 1, 0, 0))
    table.add_column(style="bold white", no_wrap=True)  # language name
    table.add_column(no_wrap=True)                       # bar
    table.add_column(justify="right", style="dim")       # file count
    table.add_column(justify="right", style="dim")       # size

    max_count = result.languages[0].file_count if result.languages else 0
    for rank, ls in enumerate(result.languages):
        table.add_row(
            _language_label(ls),
            _bar(ls.file_count, max_count, rank),
            f"{ls.file_count} files",
            _human_size(ls.total_bytes),
        )

    return Panel(
        table,
        title="[bold cyan]Languages[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )


def _build_identity_panel(result: InfoResult) -> Panel:
    h = result.heuristics

    table = Table(box=None, show_header=False, padding=(0, 2, 0, 0))
    table.add_column(style="dim", no_wrap=True)
    table.add_column()

    def row(label: str, value: str | None, style: str = "white") -> None:
        if value:
            table.add_row(label, Text(value, style=style))

    row("Type",         h.project_type or "Not a Codebase or I am still stupid :(", "bold yellow")
    row("Dependency",   h.dependency_file,                             "cyan")
    row("Entry Points", "  ".join(h.entry_points) or None,            "bright_green")
    row("Test Dirs",    "  ".join(h.test_dirs)    or None,            "white")
    row("Config Files", "  ".join(h.config_files) or None,            "dim white")

    return Panel(
        table,
        title="[bold magenta]Project Type[/bold magenta]",
        border_style="magenta",
        padding=(1, 2),
    )


def _build_largest_files_panel(result: InfoResult) -> Panel:
    table = Table(box=None, show_header=False, padding=(0, 1, 0, 0))
    table.add_column(justify="right", style="bold yellow", no_wrap=True)  # size
    table.add_column(style="white")                                         # path

    for path, size in result.largest_files:
        table.add_row(_human_size(size), path)

    return Panel(
        table,
        title="[bold yellow]Largest Files[/bold yellow]",
        border_style="yellow",
        padding=(1, 2),
    )


def render_progress(root: Path, result: InfoResult | None) -> Text:
    """Compact one-line status shown while scanning is in progress."""
    t = Text()
    t.append(" Scanning ", style="dim")
    t.append(str(root), style="dim cyan")
    if result is not None:
        t.append("  ", style="dim")
        t.append(f"{result.total_files:,}", style="bold white")
        t.append(" files  ", style="dim")
        t.append(f"{result.total_dirs:,}", style="bold white")
        t.append(" dirs  ", style="dim")
        t.append(_human_size(result.total_bytes), style="bold white")
    else:
        t.append("...", style="dim")
    return t


def render_info(result: InfoResult, console: Console) -> None:
    """Print the locus info output to the given console."""
    # ── header ──────────────────────────────────────────────────────
    header = Text()
    header.append(str(result.total_files), style="bold white")
    header.append(" files  ", style="dim")
    header.append(str(result.total_dirs), style="bold white")
    header.append(" dirs  ", style="dim")
    header.append(_human_size(result.total_bytes), style="bold white")

    console.print()
    console.print(Rule(f"[dim]{result.root}[/dim]", style="bright_black"))
    console.print(f"  {header}")
    console.print()

    # ── languages + identity side by side ───────────────────────────
    console.print(Columns(
        [_build_languages_panel(result), _build_identity_panel(result)],
        equal=False,
        expand=True,
    ))

    # ── largest files ───────────────────────────────────────────────
    if result.largest_files:
        console.print(_build_largest_files_panel(result))

    console.print()
