import os
import platform
import urllib.request
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

    def __init__(self):
        # Define where Locus will store its data
        self.locus_dir = Path.home() / ".locus"
        self.models_dir = self.locus_dir / "models"
        self.bin_dir = self.locus_dir / "bin"
        # Handle directories already existing
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
    
    def get_binary_preference(self, os_name: str, gpu_type: str, user_choice: str = "auto") -> str:
        """
        Determines which llama.cpp to download
        user_choice can be 'CUDA', 'Vulkan', 'CPU' or 'auto'.
        """
        # TODO: Map the OS and GPU type to the correct key in self.BINARIES

    def download_file():
        pass