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
    BINARIES = {
        "Windows": {
            "CUDA": "llama-bxxxx-bin-win-cuda-cu12.2-x64.zip",
            "Vulkan": "llama-bxxxx-bin-win-vulkan-x64.zip",
            "CPU": "llama-bxxxx-bin-win-avx2-x64.zip"
        },
        "Linux": {
            "CUDA": "llama-bxxxx-bin-ubuntu-x64.zip",
            "Vulkan": "llama-bxxxx-bin-ubuntu-vulkan-x64.zip",
            "CPU": "llama-bxxxx-bin-ubuntu-x64.zip"
        },
        "Darwin": {
            "APPLE_SILICON": "llama-bxxxx-bin-macos-arm64.zip"
        }
    }

    def __init__(self):
        # Define where Atlas will store its data
        self.atlas_dir = Path.home() / ".atlas"
        self.models_dir = self.atlas_dir / "models"
        self.bin_dir = self.atlas_dir / "bin"

        # TODO: Ensure these dirs exists using mkdir(parents=True, exist_ok=True)

    def determine_tier(self, ram_gb: float, gpu_type: str, vram_gb: float) -> int:
        """
        Calculates the appropriate model tier based on hardware.
        Tier 1: High-End (8GB+ VRAM or 16GB+ Apple Silicon)
        Tier 2: Mid-Range (4-6GB VRAM or 16GB+ RAM CPU)
        Tier 3: Low-End (8GB RAM CPU)
        Tier 4: Potato PC (<8GB RAM CPU)
        """
        # TODO: Implement If logic to return tier
        pass
    
    def get_binary_preference(self, os_name: str, gpu_type: str, user_choice: str = "auto") -> str:
        """
        Determines whcih llama.cpp to download
        user_choice can be 'CUDA', 'Vulkan', 'CPU' or 'auto'.
        """
        # TODO: Map the OS and GPU type to the correct key in self.BINARIES
        pass

    def download_file():
        pass