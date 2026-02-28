import argparse
from pathlib import Path
from .core.map import LocusMap
from .ui.console import console

# Keep this in sync with pyproject.toml
__version__ = "0.1.0"

def cmd_tree(args: argparse.Namespace) -> int:
    """ Handler for: `locus tree` """
    locus_map = LocusMap(args.path, args.depth, args.max_files, args.ignore) 
    tree = locus_map.generate()
    console.print(tree)
    return 0

def cmd_overview(args: argparse.Namespace) -> int:
    """ Handler for: `locus overview` """
    # TODO: think about what to show here
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="locus",
        description="Locus CLI (local codebase intelligence)"
    )

    # Arguments
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    # Subparser allow you to have commands like `locus tree` and `locus overview`
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