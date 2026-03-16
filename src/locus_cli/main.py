import argparse
from pathlib import Path
from .core.map import LocusMap
from .ui.console import console

# Keep this in sync with pyproject.toml
__version__ = "0.1.0"

def cmd_tree(args: argparse.Namespace) -> int:
    """ Handler for: `locus tree` """
    from rich.live import Live
    from rich.text import Text

    root = Path(args.path)
    locus_map = LocusMap(str(root), args.depth, args.max_files, args.ignore)

    dirs_done = [0]

    def progress() -> None:
        dirs_done[0] += 1
        t = Text()
        t.append(" Building tree ", style="dim")
        t.append(str(root), style="dim cyan")
        t.append(f"  {dirs_done[0]}", style="bold white")
        t.append(" dirs", style="dim")
        live.update(t)

    with Live(Text(f" Building tree {root}...", style="dim"), console=console, refresh_per_second=10) as live:
        tree = locus_map.generate(on_progress=progress)

    console.print(tree)
    return 0

def cmd_info(args: argparse.Namespace) -> int:
    """ Handler for: `locus info` """
    from rich.live import Live
    from .core.scanner import scan
    from .ui.info_renderer import render_info, render_progress

    root = Path(args.path)
    with Live(render_progress(root, None), console=console, refresh_per_second=10) as live:
        result = scan(root, args.ignore, on_progress=lambda r: live.update(render_progress(root, r)))

    render_info(result, console)
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="locus",
        description="Locus CLI (local codebase intelligence)"
    )

    # Arguments
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Subparser allow you to have commands like `locus tree` and `locus info`
    subparser = parser.add_subparsers(dest="command")

    # ---- tree command ----
    tree_parser = subparser.add_parser("tree", help="Show repository tree.")
    tree_parser.add_argument("path", nargs="?", default=".", help="Target Folder (default: current directory).")
    tree_parser.add_argument("--depth", type=int, default=4, help="Max traversal depth.")
    tree_parser.add_argument("--max-files", type=int, default=10, help="Max files to show for every subdir.")
    tree_parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Ignore files / folders (repeatable). Example --ignore .venv --ignore node_modules."
    )
    # If the user invokes `tree`, attach a new attribute called handler and set value to the function
    # cmd_tree()
    tree_parser.set_defaults(handler=cmd_tree)

    # ---- info command ----
    info_parser = subparser.add_parser("info", help="Show static codebase summary.")
    info_parser.add_argument("path", nargs="?", default=".", help="Target folder (default: current directory).")
    info_parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Ignore files / folders (repeatable). Example: --ignore .venv --ignore node_modules."
    )
    info_parser.set_defaults(handler=cmd_info)

    return parser

# argv=None here just means that argv is an optional parameter. but if you still provide parameters
# then argv is not going to be empty. The argparse library is hardcoded with a specific behavior:
# if it receives args=None, it automatically falls back to reading sys.argv(), which is the actual
# command line arguments provided by the OS. This design allows for dependency injection:
# - The OS calls the script, main() is executed without args, argv=None, and argparse reads the
#   real terminal inputs.
# - Testing: a test script can call main(["tree", "--depth", "2"]) and argparse sees the list,
#   ignores sys.argv and parses the injected list instead.
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # No command provided: show help and return non-zero for CLI correctness
    if not hasattr(args, "handler"):
        parser.print_help()
        return 2
    
    # Normalize target path early
    if hasattr(args, "path"):
        args.path = str(Path(args.path).expanduser().resolve())

    # If a command was provided, get the handler function() and execute it
    handler = args.handler
    return handler(args)

# The following code is run only if this specific file is run: `python main.py`, otherwise
# it won't be executed (for example importing the file won't make the following code be executed)
if __name__ == "__main__":
    raise SystemExit(main())