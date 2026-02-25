from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Callable, Sequence

# Keep this in sync with pyproject.toml
__version__ = "0.1.0a2"

def cmd_tree(args: argparse.Namespace) -> int:
    """
    Handler for: `locus tree`
    """
    # TODO: call core.map functionality
    return 0

def cmd_overview(args: argparse.Namespace):
    """
    Handler for: `locus overview`
    """
    # TODO: think about what to show here

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="locus",
        description="Locus CLI (local codebase intelligence)"
    )

    # Arguments
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparser = parser.add_subparsers(dest="command")

    # ---- tree command ----
    p_tree = subparser.add_parser("tree", help="Show repository tree.")
    p_tree.add_argument("path", nargs="?", default=".", help="Target Folder (default: current directory).")
    p_tree.add_argument("--depth", type=int, default=4, help="Max traversal depth.")
    p_tree.add_argument("--max-files", type=int, default=10, help="Max files to show for every subdir.")
    p_tree.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Ignore files / folders (repeatable). Example --ignore .venv --ignore node_modules."
    )
    p_tree.set_defaults(handler=cmd_tree)

    return parser

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # No command provided: show help and return non-zero for CLI correctness
    if not hasattr(args, "handler"):
        parser.print_help()
        return 2
    
    # Normalize target path early
    if hasattr(args, "path"):
        args.path = str(Path(args.path).expanduser().resolve())

    handler = args.handler
    return handler(args)

if __name__ == "__main__":
    raise SystemExit(main())