"""
This module provides hardware profiling capabilities.
It detects system RAM and available GPUs or AI accelerators.
"""

import psutil
import subprocess
import platform
import shutil


class HardwareProfiler:
    def get_total_ram_gb(self) -> float:
        """
        Detects the total physical RAM of the system.
        Returns the value in GB rounded to 2 decimal places
        """
        total_mem_bytes = psutil.virtual_memory().total
        total_mem = total_mem_bytes / (1024 * 1024 * 1024) # Convert from Bytes to GigaBytes
        return round(total_mem, 2)

    def detect_gpu(self) -> dict:
        """
        Attempts to detect available AI accelerators (Apple Silicon, NVIDIA, AMD).
        Returns a dictionary with 'type' and 'vram_gb' (if applicable).
        """
        # Default fallback
        gpu_info = {"type": "CPU_ONLY", "vram_gb": 0.0}

        # Get system infos
        system = platform.system()
        machine = platform.machine()

        # 1. Apple Silicon Check
        if system == "Darwin" and machine == "arm64":
            # Apple uses unified memory, so its VRAM is just the system RAM!
            vram = self.get_total_ram_gb()
            gpu_info = {"type": "APPLE_SILICON", "vram_gb": vram}

        # 2. Nvidia
        # This checks whether the nvidia driver is installed. If so, the gpu vram
        # is requested
        if shutil.which("nvidia-smi") is not None:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True
                )
            # The result.stdout will be a string like "8192\n" (in MB).
            if result.returncode == 0 and result.stdout.strip():
                # If there are multiple GPUs nvidia-smi might output more lines, so we use split()
                vram_mb = float(result.stdout.strip().split('\n')[0])
                vram_gb = round(vram_mb / 1024, 2) # Convert to GB
                gpu_info = {"type": "NVIDIA", "vram_gb": vram_gb}


        # 3. AMD Check. In this case we are not going to check VRAM since CUDA is unavailable
        # but Vulkan may be used 
        if gpu_info["type"] == "CPU_ONLY":
            try:
                if system == "Windows":
                    result = subprocess.run(
                        ["wmic", "path", "win32_VideoController", "get", "name"],
                        capture_output=True, text=True
                    )
                    if "AMD" in result.stdout.upper() or "RADEON" in result.stdout.upper():
                        gpu_info = {"type": "AMD", "vram_gb": 0.0}

                elif system == "Linux":
                    result = subprocess.run(
                        ["lspci"],
                        capture_output=True, text=True
                    )
                    if "AMD" in result.stdout.upper() or "RADEON" in result.stdout.upper():
                        gpu_info = {"type": "AMD", "vram_gb": 0.0}

            except FileNotFoundError:
                # If the AMD GPU is not found we are simply ignoring the error
                # and return the default CPU_ONLY Fallback 
                pass 


        return gpu_info



# [REMOVE LATER]
if __name__ == "__main__":
    profiler = HardwareProfiler()
    ram = profiler.get_total_ram_gb()
    gpu_info = profiler.detect_gpu()
    system = gpu_info.get("type")
    vram = gpu_info.get("vram_gb")
    print(f"System RAM detected: {ram} GB")
    print(f"System type: {system}, VRAM detected {vram} GB")