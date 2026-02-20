import psutil
import subprocess
import platform
import shutil


class HardwareProfiler:
    def __init__(self):
        pass

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

        # 1. Apple Silicon Check
        # TODO: Check if platform.system() is "Darwin" and platform.machine() is "arm64"
        # if true, set type to "APPLE_SILICON"
        # Apple uses unified memory, so its VRAM is just the system RAM!
        # (so maybe this step can be skipped?)

        # 2. Nvidia
        # TODO: Use shutil.which("nvidia-smi") to see if the Nvidia driver tool exists.
        # If it does, run this subprocess command:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True
        )
        # The result.stdout will be a string like "8192\n" (in MB).
        # Parse that into a number, convert to GB, and set type to NVIDIA

        # 3. AMD Check (?)
        # Consider if it needs implementation or not



# [REMOVE LATER]
if __name__ == "__main__":
    profiler = HardwareProfiler()
    ram = profiler.get_total_ram_gb()
    print(f"System RAM detected: {ram} GB")