"""
Textual TUI for `locus overview`.

Flow:
  1. Setup screen  — shows detected hardware, offers GPU / CPU choice.
                     If CPU-only and GPU was detected by profiler, shows
                     the pip install hint for GPU support.
  2. Pipeline      — downloads model (if not cached) then streams inference.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, ProgressBar, Static
from textual import work

from ..core.extractor import ProjectContext
from ..core.provisioner import Provisioner


class OverviewApp(App):
    CSS = """
    OverviewApp {
        background: $surface;
    }

    #hardware-panel {
        border: round $primary;
        padding: 1 2;
        margin: 1 2;
        height: auto;
    }

    #gpu-note {
        padding: 0 2;
        margin: 0 2;
        color: $warning;
        height: auto;
    }

    #controls {
        padding: 1 2;
        height: auto;
        align: center middle;
    }

    #status {
        padding: 0 2;
        color: $text-muted;
        height: auto;
    }

    #progress-bar {
        margin: 1 2;
    }

    #output {
        border: round $success;
        margin: 1 2;
        padding: 1 2;
        height: 1fr;
        overflow-y: scroll;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    # Phase drives what is visible: setup | pipeline | done
    phase: reactive[str] = reactive("setup")

    def __init__(
        self,
        scan_path: Path,
        context: ProjectContext,
        tier: int,
        provisioner: Provisioner,
        gpu_info: dict,
    ) -> None:
        super().__init__()
        self.scan_path = scan_path
        self.context = context
        self.tier = tier
        self.provisioner = provisioner
        self.gpu_info = gpu_info
        self._gpu_supported = self._detect_gpu_support()
        self._n_gpu_layers = 0
        self._output_buf: list[str] = []

    @staticmethod
    def _detect_gpu_support() -> bool:
        from ..core.inference import check_gpu_support
        return check_gpu_support()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Vertical(
            Static(id="hardware-panel"),
            Static(id="gpu-note"),
            Horizontal(
                Button("Use GPU  [G]", id="btn-gpu", variant="success"),
                Button("Use CPU  [C]", id="btn-cpu", variant="default"),
                id="controls",
            ),
            Static(id="status"),
            ProgressBar(id="progress-bar", total=100, show_eta=True),
            Static(id="output"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self._render_setup()

    def _render_setup(self) -> None:
        gpu_type: str = str(self.gpu_info.get("type", "CPU_ONLY"))
        vram: float = float(self.gpu_info.get("vram_gb", 0.0))
        model_name, _ = self.provisioner.MODELS[self.tier]
        cached = self.provisioner.is_model_cached(self.tier)

        lines = ["[bold]Hardware[/bold]\n"]
        if gpu_type == "APPLE_SILICON":
            lines.append(f"  GPU   Apple Silicon  ({vram:.0f} GB unified)")
        elif gpu_type not in ("CPU_ONLY", ""):
            vram_str = f"  ·  {vram:.1f} GB VRAM" if vram > 0 else ""
            lines.append(f"  GPU   {gpu_type}{vram_str}")
        else:
            lines.append("  GPU   Not detected")

        lines.append(f"\n[bold]Model[/bold]  {model_name}  (Tier {self.tier})")
        if cached:
            lines.append("         [dim](cached)[/dim]")

        self.query_one("#hardware-panel", Static).update("\n".join(lines))

        has_gpu = gpu_type not in ("CPU_ONLY", "")

        if has_gpu and self._gpu_supported:
            # Offer the choice
            self.query_one("#gpu-note", Static).display = False
            self.query_one("#progress-bar", ProgressBar).display = False
            self.query_one("#output", Static).display = False
            self.query_one("#status", Static).update(
                "[dim]Choose how to run inference:[/dim]"
            )
        elif has_gpu and not self._gpu_supported:
            # GPU detected but llama-cpp-python compiled without GPU support
            from ..core.inference import gpu_install_hint
            hint = gpu_install_hint(gpu_type) or ""
            self.query_one("#gpu-note", Static).update(
                f"[yellow]GPU detected but llama-cpp-python has no GPU support.\n"
                f"To enable it:\n  {hint}[/yellow]"
            )
            self.query_one("#controls", Horizontal).display = False
            self.query_one("#progress-bar", ProgressBar).display = False
            self.query_one("#output", Static).display = False
            self.query_one("#status", Static).update(
                "[dim]Running on CPU.  Press [bold]Enter[/bold] to continue.[/dim]"
            )
        else:
            # Pure CPU
            self.query_one("#gpu-note", Static).display = False
            self.query_one("#controls", Horizontal).display = False
            self.query_one("#progress-bar", ProgressBar).display = False
            self.query_one("#output", Static).display = False
            self.query_one("#status", Static).update(
                "[dim]No GPU detected — running on CPU.  "
                "Press [bold]Enter[/bold] to continue.[/dim]"
            )

    # ------------------------------------------------------------------ #
    # Input handling
    # ------------------------------------------------------------------ #

    def on_key(self, event) -> None:
        if self.phase != "setup":
            return
        key = event.key
        if key == "enter":
            self._start_pipeline(n_gpu_layers=0)
        elif key == "g" and self._gpu_supported:
            self._start_pipeline(n_gpu_layers=-1)
        elif key == "c":
            self._start_pipeline(n_gpu_layers=0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.phase != "setup":
            return
        if event.button.id == "btn-gpu":
            self._start_pipeline(n_gpu_layers=-1)
        elif event.button.id == "btn-cpu":
            self._start_pipeline(n_gpu_layers=0)

    # ------------------------------------------------------------------ #
    # Pipeline
    # ------------------------------------------------------------------ #

    def _start_pipeline(self, n_gpu_layers: int) -> None:
        self._n_gpu_layers = n_gpu_layers
        self.phase = "pipeline"
        self.query_one("#controls", Horizontal).display = False
        self.query_one("#gpu-note", Static).display = False
        self._run_pipeline()

    @work(thread=True)
    def _run_pipeline(self) -> None:
        from ..core.inference import stream_overview

        status = self.query_one("#status", Static)
        output = self.query_one("#output", Static)
        progress = self.query_one("#progress-bar", ProgressBar)
        try:
            self._pipeline_body(stream_overview, status, output, progress)
        except Exception as exc:
            self.call_from_thread(
                status.update,
                f"[red bold]Error:[/red bold] [red]{exc}[/red]\n\n"
                "[dim]Press [bold]q[/bold] to quit.[/dim]",
            )
            self.phase = "done"
            return

    def _pipeline_body(self, stream_overview, status, output, progress) -> None:

        # ── Step 1: download model if needed ──────────────────────────
        if not self.provisioner.is_model_cached(self.tier):
            model_name, _ = self.provisioner.MODELS[self.tier]
            self.call_from_thread(
                status.update, f"[dim]Downloading {model_name}...[/dim]"
            )

            def _on_progress(downloaded: int, total: int) -> None:
                mb = downloaded / (1024 * 1024)
                if total > 0:
                    pct = int(downloaded / total * 100)
                    total_mb = total / (1024 * 1024)
                    self.call_from_thread(
                        status.update,
                        f"[dim]Downloading {model_name}...  "
                        f"{mb:.0f} / {total_mb:.0f} MB  ({pct}%)[/dim]",
                    )
                    self.call_from_thread(progress.update, progress=pct)
                else:
                    # Server didn't send Content-Length — show bytes only
                    self.call_from_thread(
                        status.update,
                        f"[dim]Downloading {model_name}...  {mb:.0f} MB[/dim]",
                    )

            self.call_from_thread(setattr, progress, "display", True)
            self.provisioner.download_model(self.tier, on_progress=_on_progress)
            self.call_from_thread(setattr, progress, "display", False)

        # ── Step 2: stream inference ───────────────────────────────────
        self.call_from_thread(
            status.update, "[dim]Loading model and generating overview...[/dim]"
        )
        self.call_from_thread(setattr, output, "display", True)

        def _on_token(token: str) -> None:
            self._output_buf.append(token)
            # Refresh the display every 8 tokens to avoid hammering the UI
            if len(self._output_buf) % 8 == 0:
                text = "".join(self._output_buf)
                self.call_from_thread(output.update, text)

        stream_overview(
            model_path=self.provisioner.get_model_path(self.tier),
            ctx=self.context,
            n_gpu_layers=self._n_gpu_layers,
            on_token=_on_token,
        )

        # Final flush
        self.call_from_thread(output.update, "".join(self._output_buf))
        self.call_from_thread(
            status.update,
            "[green]Done.[/green]  Press [bold]q[/bold] to quit.",
        )
        self.phase = "done"
