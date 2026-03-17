import platform
import urllib.request
from collections.abc import Callable
from pathlib import Path

class Provisioner:
    """
    Maps Hardware profiles to specific AI models and inference binaries,
    and handles downloading them to the local system.
    """

    # Model Matrix
    # Format: {Tier: (Filename, HuggingFace Download URL)}
    MODELS = {
        1: ("qwen2.5-coder-7b-instruct-q4_k_m.gguf", "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"),
        2: ("qwen2.5-coder-3b-instruct-q4_k_m.gguf", "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf"),
        3: ("qwen2.5-coder-1.5b-instruct-q4_k_m.gguf", "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"),
        4: ("qwen2.5-coder-0.5b-instruct-q4_k_m.gguf", "https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf")
    }


    # The Binary Matrix (llama.cpp server releases)
    # URLS will need to be updated to the latest release tag
    # TODO: Port later to manifest.json
    BINARIES = {
        "Windows": {
            "CUDA": "https://github.com/ggml-org/llama.cpp/releases/download/b8133/llama-b8133-bin-win-cuda-13.1-x64.zip",
            "Vulkan": "https://github.com/ggml-org/llama.cpp/releases/download/b8133/llama-b8133-bin-win-vulkan-x64.zip",
            "CPU": "https://github.com/ggml-org/llama.cpp/releases/download/b8133/llama-b8133-bin-win-cpu-x64.zip"
        },
        "Linux": {
            "CUDA": "https://github.com/ggml-org/llama.cpp/releases/download/b8133/llama-b8133-bin-ubuntu-x64.tar.gz",
            "Vulkan": "https://github.com/ggml-org/llama.cpp/releases/download/b8133/llama-b8133-bin-ubuntu-vulkan-x64.tar.gz",
            "CPU": "https://github.com/ggml-org/llama.cpp/releases/download/b8133/llama-b8133-bin-ubuntu-x64.tar.gz"
        },
        "Darwin": {
            "APPLE_SILICON": "https://github.com/ggml-org/llama.cpp/releases/download/b8133/llama-b8133-bin-macos-arm64.tar.gz"
        }
    }

    def __init__(self, locus_dir: Path | None = None) -> None:
        self.locus_dir = locus_dir or (Path.home() / ".locus")
        self.models_dir = self.locus_dir / "models"
        self.bin_dir = self.locus_dir / "bin"
        self.locus_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.bin_dir.mkdir(parents=True, exist_ok=True)

    def determine_tier(self, ram_gb: float, gpu_type: str, vram_gb: float) -> int:
        """
        Calculates the appropriate model tier based on hardware.
        Tier 1: High-End (8GB+ VRAM or 16GB+ Apple Silicon)
        Tier 2: Mid-Range (4-6GB VRAM or 16GB+ RAM CPU)
        Tier 3: Low-End (8GB RAM CPU)
        Tier 4: Potato PC (<8GB RAM CPU)
        """
        gpu = (gpu_type or "").upper()

        # Apple Silicon
        if gpu == "APPLE_SILICON":
            if ram_gb >= 16:
                return 1
            if ram_gb >= 8:
                return 3
            return 4
        
        # Discrete GPU
        if vram_gb >= 8:
            return 1
        if vram_gb >= 4:
            return 2
        
        # CPU only
        if ram_gb >= 16:
            return 2
        if ram_gb >= 8:
            return 3
        
        # Default case - Tier 4
        return 4
    
    def get_model_path(self, tier: int) -> Path:
        """Return the local path where the model for this tier is (or would be) stored."""
        filename, _ = self.MODELS[tier]
        return self.models_dir / filename

    def is_model_cached(self, tier: int) -> bool:
        """Return True if the model file for this tier already exists on disk."""
        return self.get_model_path(tier).exists()

    def download_model(
        self,
        tier: int,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """
        Download the GGUF model for the given tier to ~/.locus/models/.
        Downloads to a .tmp file first and renames on success (atomic).

        on_progress: called with (bytes_downloaded, total_bytes).
        """
        dest = self.get_model_path(tier)
        if dest.exists():
            return dest

        _, url = self.MODELS[tier]
        tmp = dest.with_suffix(".tmp")

        def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
            if on_progress and total_size > 0:
                downloaded = min(block_num * block_size, total_size)
                on_progress(downloaded, total_size)

        try:
            urllib.request.urlretrieve(url, str(tmp), _reporthook)
            tmp.rename(dest)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

        return dest