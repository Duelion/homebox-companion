"""GPU detection service for optimal AI model selection.

Detects available GPUs (NVIDIA, AMD, Intel) and their capabilities
to help recommend appropriate Ollama models based on VRAM.

Usage:
    detector = GPUDetector()
    info = detector.detect()
    print(info.vendor, info.name, info.vram_mb)
    print(info.recommended_model)
"""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class GPUVendor(str, Enum):
    """GPU vendor identification."""

    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    APPLE = "apple"  # Apple Silicon
    UNKNOWN = "unknown"
    NONE = "none"  # No GPU detected


@dataclass
class GPUInfo:
    """Information about a detected GPU."""

    vendor: GPUVendor = GPUVendor.NONE
    name: str = ""
    vram_mb: int = 0
    driver_version: str = ""
    cuda_version: str = ""  # NVIDIA only
    compute_capability: str = ""  # NVIDIA only
    detected: bool = False
    detection_method: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def vram_gb(self) -> float:
        """VRAM in gigabytes."""
        return self.vram_mb / 1024 if self.vram_mb > 0 else 0.0

    @property
    def recommended_model(self) -> str:
        """Recommend an Ollama model based on VRAM.

        Returns:
            Model name recommendation based on available VRAM.
        """
        if self.vram_mb >= 48000:  # 48GB+
            return "llama3.2-vision:90b"
        elif self.vram_mb >= 8000:  # 8GB+
            return "llama3.2-vision:11b"
        elif self.vram_mb >= 6000:  # 6GB+
            return "minicpm-v"
        elif self.vram_mb >= 4000:  # 4GB+
            return "granite3.2-vision"
        elif self.vram_mb >= 3000:  # 3GB+
            return "moondream"
        else:
            # CPU-only or low VRAM - recommend smallest model
            return "moondream"

    @property
    def supports_vision_models(self) -> bool:
        """Check if GPU can run vision models effectively."""
        return self.vram_mb >= 3000 or self.vendor == GPUVendor.APPLE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "detected": self.detected,
            "vendor": self.vendor.value,
            "name": self.name,
            "vram_mb": self.vram_mb,
            "vram_gb": round(self.vram_gb, 1),
            "driver_version": self.driver_version,
            "cuda_version": self.cuda_version,
            "compute_capability": self.compute_capability,
            "recommended_model": self.recommended_model,
            "supports_vision_models": self.supports_vision_models,
            "detection_method": self.detection_method,
        }


class GPUDetector:
    """Detect and report GPU capabilities.

    Supports detection of:
    - NVIDIA GPUs via nvidia-smi
    - AMD GPUs via rocm-smi (Linux) or Windows registry
    - Intel GPUs via basic detection
    - Apple Silicon via system_profiler
    """

    def detect(self) -> GPUInfo:
        """Detect the primary GPU in the system.

        Returns:
            GPUInfo with detected GPU details, or empty info if none found.
        """
        # Try detection methods in order of preference
        detectors = [
            self._detect_nvidia,
            self._detect_amd,
            self._detect_apple_silicon,
            self._detect_intel,
        ]

        for detector in detectors:
            try:
                info = detector()
                if info and info.detected:
                    logger.info(
                        f"GPU detected: {info.vendor.value} {info.name} "
                        f"({info.vram_gb:.1f}GB VRAM)"
                    )
                    return info
            except Exception as e:
                logger.debug(f"GPU detection method failed: {e}")

        logger.info("No GPU detected, will use CPU for inference")
        return GPUInfo(detected=False, detection_method="none")

    def detect_all(self) -> list[GPUInfo]:
        """Detect all GPUs in the system.

        Returns:
            List of GPUInfo for all detected GPUs.
        """
        gpus = []

        # Try each detection method
        try:
            nvidia_gpus = self._detect_nvidia_all()
            gpus.extend(nvidia_gpus)
        except Exception as e:
            logger.debug(f"NVIDIA detection failed: {e}")

        try:
            amd_gpu = self._detect_amd()
            if amd_gpu and amd_gpu.detected:
                gpus.append(amd_gpu)
        except Exception as e:
            logger.debug(f"AMD detection failed: {e}")

        try:
            apple_gpu = self._detect_apple_silicon()
            if apple_gpu and apple_gpu.detected:
                gpus.append(apple_gpu)
        except Exception as e:
            logger.debug(f"Apple Silicon detection failed: {e}")

        return gpus

    def _detect_nvidia(self) -> GPUInfo | None:
        """Detect NVIDIA GPU using nvidia-smi."""
        try:
            # Query GPU info
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version,compute_cap",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return None

            line = result.stdout.strip().split("\n")[0]
            if not line:
                return None

            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                return None

            name = parts[0]
            vram_mb = int(float(parts[1])) if parts[1] else 0
            driver = parts[2] if len(parts) > 2 else ""
            compute = parts[3] if len(parts) > 3 else ""

            # Get CUDA version
            cuda_version = self._get_cuda_version()

            return GPUInfo(
                vendor=GPUVendor.NVIDIA,
                name=name,
                vram_mb=vram_mb,
                driver_version=driver,
                cuda_version=cuda_version,
                compute_capability=compute,
                detected=True,
                detection_method="nvidia-smi",
                raw_data={"output": result.stdout},
            )

        except FileNotFoundError:
            logger.debug("nvidia-smi not found")
            return None
        except Exception as e:
            logger.debug(f"NVIDIA detection error: {e}")
            return None

    def _detect_nvidia_all(self) -> list[GPUInfo]:
        """Detect all NVIDIA GPUs."""
        gpus = []
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,driver_version,compute_cap",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return gpus

            cuda_version = self._get_cuda_version()

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 4:
                    continue

                gpus.append(
                    GPUInfo(
                        vendor=GPUVendor.NVIDIA,
                        name=parts[1],
                        vram_mb=int(float(parts[2])) if parts[2] else 0,
                        driver_version=parts[3],
                        cuda_version=cuda_version,
                        compute_capability=parts[4] if len(parts) > 4 else "",
                        detected=True,
                        detection_method="nvidia-smi",
                    )
                )

        except Exception as e:
            logger.debug(f"NVIDIA multi-GPU detection error: {e}")

        return gpus

    def _get_cuda_version(self) -> str:
        """Get CUDA version from nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # nvidia-smi output includes CUDA version in header
            # Try to get it from a different command
            result2 = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            # Parse CUDA version from output like "CUDA Version: 12.4"
            match = re.search(r"CUDA Version:\s*(\d+\.\d+)", result2.stdout)
            if match:
                return match.group(1)
        except Exception:
            pass
        return ""

    def _detect_amd(self) -> GPUInfo | None:
        """Detect AMD GPU using rocm-smi or system commands."""
        # Try rocm-smi first (Linux with ROCm)
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--showmeminfo", "vram"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                output = result.stdout

                # Parse product name
                name_match = re.search(r"Card series:\s*(.+)", output)
                name = name_match.group(1).strip() if name_match else "AMD GPU"

                # Parse VRAM
                vram_match = re.search(r"VRAM Total Memory \(B\):\s*(\d+)", output)
                vram_mb = int(vram_match.group(1)) // (1024 * 1024) if vram_match else 0

                return GPUInfo(
                    vendor=GPUVendor.AMD,
                    name=name,
                    vram_mb=vram_mb,
                    detected=True,
                    detection_method="rocm-smi",
                    raw_data={"output": output},
                )

        except FileNotFoundError:
            logger.debug("rocm-smi not found")
        except Exception as e:
            logger.debug(f"ROCm detection error: {e}")

        # Try Windows WMI detection
        if platform.system() == "Windows":
            return self._detect_amd_windows()

        return None

    def _detect_amd_windows(self) -> GPUInfo | None:
        """Detect AMD GPU on Windows using WMIC."""
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_videocontroller", "get", "name,adapterram"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "AMD" in line or "Radeon" in line:
                        # Parse name and VRAM
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            vram_bytes = 0
                            name_parts = []
                            for part in parts:
                                if part.isdigit():
                                    vram_bytes = int(part)
                                else:
                                    name_parts.append(part)

                            return GPUInfo(
                                vendor=GPUVendor.AMD,
                                name=" ".join(name_parts),
                                vram_mb=vram_bytes // (1024 * 1024),
                                detected=True,
                                detection_method="wmic",
                            )

        except Exception as e:
            logger.debug(f"Windows AMD detection error: {e}")

        return None

    def _detect_apple_silicon(self) -> GPUInfo | None:
        """Detect Apple Silicon GPU."""
        if platform.system() != "Darwin":
            return None

        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return None

            output = result.stdout

            # Check for Apple Silicon
            if "Apple M" in output:
                # Parse chip name
                chip_match = re.search(r"Chipset Model:\s*(Apple M\d+\s*\w*)", output)
                name = chip_match.group(1) if chip_match else "Apple Silicon"

                # Apple Silicon uses unified memory
                # Try to get total system memory as an approximation
                mem_result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                total_mem_mb = 0
                if mem_result.returncode == 0:
                    total_mem_bytes = int(mem_result.stdout.strip())
                    # Apple Silicon shares memory, assume ~70% available for GPU
                    total_mem_mb = int((total_mem_bytes / (1024 * 1024)) * 0.7)

                return GPUInfo(
                    vendor=GPUVendor.APPLE,
                    name=name,
                    vram_mb=total_mem_mb,
                    detected=True,
                    detection_method="system_profiler",
                    raw_data={"output": output},
                )

        except Exception as e:
            logger.debug(f"Apple Silicon detection error: {e}")

        return None

    def _detect_intel(self) -> GPUInfo | None:
        """Detect Intel GPU (basic detection)."""
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["wmic", "path", "win32_videocontroller", "get", "name,adapterram"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "Intel" in line:
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                vram_bytes = 0
                                name_parts = []
                                for part in parts:
                                    if part.isdigit():
                                        vram_bytes = int(part)
                                    else:
                                        name_parts.append(part)

                                return GPUInfo(
                                    vendor=GPUVendor.INTEL,
                                    name=" ".join(name_parts),
                                    vram_mb=vram_bytes // (1024 * 1024),
                                    detected=True,
                                    detection_method="wmic",
                                )

            except Exception as e:
                logger.debug(f"Intel GPU detection error: {e}")

        return None


# Module-level singleton for convenience
_detector: GPUDetector | None = None


def get_gpu_detector() -> GPUDetector:
    """Get the singleton GPU detector instance."""
    global _detector
    if _detector is None:
        _detector = GPUDetector()
    return _detector


def detect_gpu() -> GPUInfo:
    """Convenience function to detect primary GPU.

    Returns:
        GPUInfo for the detected GPU.
    """
    return get_gpu_detector().detect()
