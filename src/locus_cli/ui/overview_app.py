"""
Textual TUI for `locus overview` — setup screen only.

Shows detected hardware and asks the user whether to run on GPU or CPU.
Returns n_gpu_layers (-1 = full GPU offload, 0 = CPU) via app.run().

After the app exits, the caller (cmd_overview) handles model download and
streams inference output directly to the terminal.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from ..core.provisioner import Provisioner


class OverviewApp(App[int]):
    """Setup screen: display hardware info and collect GPU/CPU preference."""

    CSS = """
    OverviewApp {
        background: $surface;
        align: center middle;
    }

    #panel {
        border: round $primary;
        padding: 1 3;
        width: 64;
        height: auto;
    }

    #hardware {
        height: auto;
        margin-bottom: 1;
    }

    #note {
        color: $warning;
        height: auto;
        margin-bottom: 1;
    }

    #status {
        color: $text-muted;
        height: auto;
    }

    #controls {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        tier: int,
        provisioner: Provisioner,
        gpu_info: dict,
    ) -> None:
        super().__init__()
        self.tier = tier
        self.provisioner = provisioner
        self.gpu_info = gpu_info
        gpu_type: str = str(gpu_info.get("type", "CPU_ONLY"))
        self._has_gpu = gpu_type not in ("CPU_ONLY", "")
        self._gpu_type = gpu_type
        self._gpu_supported = self._detect_gpu_support()

    @staticmethod
    def _detect_gpu_support() -> bool:
        from ..core.inference import check_gpu_support
        return check_gpu_support()

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static(id="hardware")
            yield Static(id="note")
            yield Static(id="status")
            with Horizontal(id="controls"):
                yield Button("GPU  [G]", id="btn-gpu", variant="success")
                yield Button("CPU  [C]", id="btn-cpu", variant="default")

    def on_mount(self) -> None:
        vram: float = float(self.gpu_info.get("vram_gb", 0.0))
        model_name, _ = self.provisioner.MODELS[self.tier]
        cached = self.provisioner.is_model_cached(self.tier)

        # Hardware line
        if self._gpu_type == "APPLE_SILICON":
            gpu_line = f"  GPU    Apple Silicon  ({vram:.0f} GB unified)"
        elif self._has_gpu:
            vram_str = f"  ·  {vram:.1f} GB VRAM" if vram > 0 else ""
            gpu_line = f"  GPU    {self._gpu_type}{vram_str}"
        else:
            gpu_line = "  GPU    Not detected"

        cache_tag = "  [dim](cached)[/dim]" if cached else ""
        self.query_one("#hardware", Static).update(
            f"[bold]Hardware[/bold]\n{gpu_line}\n\n"
            f"[bold]Model[/bold]   {model_name}  (Tier {self.tier}){cache_tag}"
        )

        note = self.query_one("#note", Static)
        status = self.query_one("#status", Static)
        controls = self.query_one("#controls", Horizontal)

        if not self._has_gpu:
            # No GPU hardware detected — CPU only, no choice needed
            note.display = False
            controls.display = False
            status.update(
                "[dim]No GPU detected — running on CPU.\n"
                "Press [bold]Enter[/bold] to continue.[/dim]"
            )
        elif not self._gpu_supported:
            # GPU hardware found but llama-cpp-python may lack GPU support.
            # Still offer the choice — llama.cpp silently falls back to CPU if
            # GPU offload isn't available, so letting the user try is safe.
            from ..core.inference import gpu_install_hint
            hint = gpu_install_hint(self._gpu_type) or ""
            note.update(
                f"[yellow]llama-cpp-python may not have GPU support compiled in.\n"
                f"To enable it:  {hint}[/yellow]"
            )
            status.update("[dim]Choose how to run inference:[/dim]")
        else:
            # GPU hardware + GPU support confirmed
            note.display = False
            status.update("[dim]Choose how to run inference:[/dim]")

    # ------------------------------------------------------------------ #
    # Input
    # ------------------------------------------------------------------ #

    def on_key(self, event) -> None:
        key = event.key
        if key == "h" and self._has_gpu:
            self.query_one("#btn-gpu", Button).focus()
        elif key == "l" and self._has_gpu:
            self.query_one("#btn-cpu", Button).focus()
        elif key == "g" and self._has_gpu:
            self.exit(-1)
        elif key == "c":
            self.exit(0)
        elif key == "enter" and not self._has_gpu:
            # No buttons visible — Enter confirms CPU-only run
            self.exit(0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-gpu" and self._has_gpu:
            self.exit(-1)
        elif event.button.id == "btn-cpu":
            self.exit(0)
