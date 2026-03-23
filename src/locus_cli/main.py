import argparse
from pathlib import Path
from .core.map import LocusMap
from .ui.console import console

# Keep this in sync with pyproject.toml
__version__ = "0.1.0"

def cmd_tree(args: argparse.Namespace) -> int:
    """ Handler for: `locus tree` """
    locus_map = LocusMap(args.path, args.depth, args.max_files, args.ignore)
    with console.status(f"[dim]Scanning {args.path}[/]", spinner="dots"):
        tree = locus_map.generate()
    console.rule(f"[dim]{args.path}[/]")
    console.print(tree)
    return 0

def cmd_info(args: argparse.Namespace) -> int:
    """ Handler for: `locus info` """
    from rich.live import Live
    from .core.scanner import scan
    from .ui.info_renderer import render_info, render_progress
    path = Path(args.path)
    with Live(console=console, refresh_per_second=10) as live:
        result = scan(path, args.ignore, on_progress=lambda r: live.update(render_progress(path, r)))
        live.update(render_progress(path, result))
    render_info(result, console)
    return 0


def cmd_overview(args: argparse.Namespace) -> int:
    """ Handler for: `locus overview` — setup TUI, then streams to terminal """
    from .core.scanner import scan
    from .core.extractor import extract_context
    from .core.profiler import HardwareProfiler
    from .core.provisioner import Provisioner
    from .core.inference import stream_overview
    from .ui.overview_app import OverviewApp
    from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

    path = Path(args.path)

    # Pre-flight: scan + context extraction before opening TUI
    with console.status("[dim]Scanning codebase...[/]", spinner="dots"):
        result = scan(path, args.ignore)
        context = extract_context(path, result)

    profiler = HardwareProfiler()
    gpu_info = profiler.detect_gpu()
    ram_gb = profiler.get_total_ram_gb()

    provisioner = Provisioner()
    tier = provisioner.determine_tier(
        ram_gb=ram_gb,
        gpu_type=str(gpu_info.get("type", "CPU_ONLY")),
        vram_gb=float(gpu_info.get("vram_gb", 0.0)),
    )

    # Setup screen: user picks GPU or CPU, app returns n_gpu_layers
    app = OverviewApp(tier=tier, provisioner=provisioner, gpu_info=gpu_info)
    n_gpu_layers: int = app.run() or 0

    # Download model if not cached (Rich progress bar, no TUI)
    if not provisioner.is_model_cached(tier):
        model_name, _ = provisioner.MODELS[tier]
        with Progress(
            "[dim]{task.description}[/dim]",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task(f"Downloading {model_name}", total=None)

            def _on_dl(downloaded: int, total: int) -> None:
                progress.update(task_id, completed=downloaded, total=total if total > 0 else None)

            provisioner.download_model(tier, on_progress=_on_dl)

    # Stream inference, re-rendering as markdown every 15 tokens
    from rich.live import Live
    from rich.markdown import Markdown

    buf: list[str] = []
    console.rule("[dim]Overview[/dim]")
    with Live(Markdown(""), console=console, refresh_per_second=6, vertical_overflow="visible") as live:
        def _on_token(token: str) -> None:
            buf.append(token)
            if len(buf) % 5 == 0:
                live.update(Markdown("".join(buf)))

        stream_overview(
            model_path=provisioner.get_model_path(tier),
            ctx=context,
            n_gpu_layers=n_gpu_layers,
            on_token=_on_token,
        )
        live.update(Markdown("".join(buf)))  # final flush

    console.rule()
    return 0


def cmd_tutor(args: argparse.Namespace) -> int:
    """ Handler for: `locus tutor` """
    from .core.tutor import TutorSession
    from .core.profiler import HardwareProfiler
    from .core.provisioner import Provisioner
    from .core.inference import check_gpu_support
    from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

    file_path = Path(args.file).expanduser().resolve()

    # Validate file before provisioning (fast fail)
    try:
        TutorSession(file_path, n_gpu_layers=0, _skip_workers=True)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    # Hardware profiling + tier selection
    with console.status("[dim]Profiling hardware...[/dim]", spinner="dots"):
        profiler = HardwareProfiler()
        gpu_info = profiler.detect_gpu()
        ram_gb = profiler.get_total_ram_gb()
        provisioner = Provisioner()
        tier = provisioner.determine_tier(
            ram_gb=ram_gb,
            gpu_type=str(gpu_info.get("type", "CPU_ONLY")),
            vram_gb=float(gpu_info.get("vram_gb", 0.0)),
        )

    # Auto-select n_gpu_layers (no user prompt)
    with console.status("[dim]Initializing AI backend...[/dim]", spinner="dots"):
        n_gpu_layers = -1 if check_gpu_support() else 0

    # Model download advisory + download if needed
    _MODEL_SIZES = {1: "4.7 GB", 2: "2.0 GB", 3: "1.0 GB", 4: "0.4 GB"}
    if not provisioner.is_model_cached(tier):
        model_name, _ = provisioner.MODELS[tier]
        model_size = _MODEL_SIZES.get(tier, "several GB")
        console.print(
            f"\n[bold]Model required:[/bold] {model_name}  (~{model_size})\n"
            f"[dim]Saved to: ~/.locus/models/{model_name}[/dim]\n"
            f"[yellow]This download may be slow depending on your connection speed.[/yellow]\n"
        )
        with Progress(
            "[dim]{task.description}[/dim]",
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task(f"Downloading {model_name}", total=None)
            def _on_dl(downloaded: int, total: int) -> None:
                progress.update(task_id, completed=downloaded, total=total if total > 0 else None)
            provisioner.download_model(tier, on_progress=_on_dl)

    # Launch TUI
    from .ui.tutor_app import TutorApp
    app = TutorApp(
        file_path=file_path,
        model_path=provisioner.get_model_path(tier),
        n_gpu_layers=n_gpu_layers,
    )
    app.run()
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

    # ---- info command ----
    info_parser = subparser.add_parser("info", help="Show static codebase analysis.")
    info_parser.add_argument("path", nargs="?", default=".", help="Target folder (default: current directory).")
    info_parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Ignore files / folders (repeatable)."
    )
    info_parser.set_defaults(handler=cmd_info)

    # ---- overview command ----
    overview_parser = subparser.add_parser("overview", help="AI-powered codebase overview (local LLM).")
    overview_parser.add_argument("path", nargs="?", default=".", help="Target folder (default: current directory).")
    overview_parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Ignore files / folders (repeatable)."
    )
    overview_parser.set_defaults(handler=cmd_overview)

    # ---- tutor command ----
    tutor_parser = subparser.add_parser("tutor", help="Line-by-line AI code tutor.")
    tutor_parser.add_argument("file", help="File to tutor.")
    tutor_parser.set_defaults(handler=cmd_tutor)

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