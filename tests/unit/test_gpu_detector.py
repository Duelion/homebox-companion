"""Unit tests for GPU detector service.

Tests cover:
- GPU info data class
- Model recommendations based on VRAM
- Detection methods (mocked)
"""

from __future__ import annotations

import pytest

from homebox_companion.services.gpu_detector import (
    GPUDetector,
    GPUInfo,
    GPUVendor,
    detect_gpu,
)

pytestmark = [pytest.mark.unit]


class TestGPUInfo:
    """Tests for GPUInfo data class."""

    def test_vram_gb_calculation(self) -> None:
        """VRAM is correctly converted to GB."""
        info = GPUInfo(vram_mb=8192)
        assert info.vram_gb == 8.0

    def test_vram_gb_zero(self) -> None:
        """Zero VRAM returns zero GB."""
        info = GPUInfo(vram_mb=0)
        assert info.vram_gb == 0.0

    def test_recommended_model_high_vram(self) -> None:
        """High VRAM recommends large model."""
        info = GPUInfo(vram_mb=49152)  # 48GB
        assert info.recommended_model == "llama3.2-vision:90b"

    def test_recommended_model_8gb(self) -> None:
        """8GB VRAM recommends 11b model."""
        info = GPUInfo(vram_mb=8192)
        assert info.recommended_model == "llama3.2-vision:11b"

    def test_recommended_model_6gb(self) -> None:
        """6GB VRAM recommends minicpm-v."""
        info = GPUInfo(vram_mb=6144)
        assert info.recommended_model == "minicpm-v"

    def test_recommended_model_4gb(self) -> None:
        """4GB VRAM recommends granite."""
        info = GPUInfo(vram_mb=4096)
        assert info.recommended_model == "granite3.2-vision"

    def test_recommended_model_3gb(self) -> None:
        """3GB VRAM recommends moondream."""
        info = GPUInfo(vram_mb=3072)
        assert info.recommended_model == "moondream"

    def test_recommended_model_low_vram(self) -> None:
        """Low VRAM recommends moondream."""
        info = GPUInfo(vram_mb=2048)
        assert info.recommended_model == "moondream"

    def test_supports_vision_with_sufficient_vram(self) -> None:
        """3GB+ VRAM supports vision models."""
        info = GPUInfo(vram_mb=3072)
        assert info.supports_vision_models is True

    def test_supports_vision_insufficient_vram(self) -> None:
        """Less than 3GB VRAM doesn't support vision well."""
        info = GPUInfo(vram_mb=2048)
        assert info.supports_vision_models is False

    def test_supports_vision_apple_silicon(self) -> None:
        """Apple Silicon always supports vision (unified memory)."""
        info = GPUInfo(vendor=GPUVendor.APPLE, vram_mb=0)
        assert info.supports_vision_models is True

    def test_to_dict(self) -> None:
        """to_dict returns expected structure."""
        info = GPUInfo(
            vendor=GPUVendor.NVIDIA,
            name="RTX 3080",
            vram_mb=10240,
            driver_version="535.104",
            cuda_version="12.2",
            detected=True,
            detection_method="nvidia-smi",
        )

        result = info.to_dict()

        assert result["detected"] is True
        assert result["vendor"] == "nvidia"
        assert result["name"] == "RTX 3080"
        assert result["vram_mb"] == 10240
        assert result["vram_gb"] == 10.0
        assert result["driver_version"] == "535.104"
        assert result["cuda_version"] == "12.2"
        assert result["recommended_model"] == "llama3.2-vision:11b"
        assert result["supports_vision_models"] is True

    def test_to_dict_no_gpu(self) -> None:
        """to_dict works when no GPU detected."""
        info = GPUInfo(detected=False)

        result = info.to_dict()

        assert result["detected"] is False
        assert result["vendor"] == "none"


class TestGPUDetector:
    """Tests for GPUDetector class."""

    def test_detect_returns_gpu_info(self) -> None:
        """detect() returns a GPUInfo instance."""
        detector = GPUDetector()
        result = detector.detect()

        assert isinstance(result, GPUInfo)

    def test_detect_all_returns_list(self) -> None:
        """detect_all() returns a list of GPUInfo."""
        detector = GPUDetector()
        result = detector.detect_all()

        assert isinstance(result, list)

    def test_singleton_detector(self) -> None:
        """get_gpu_detector returns singleton."""
        from homebox_companion.services.gpu_detector import get_gpu_detector

        d1 = get_gpu_detector()
        d2 = get_gpu_detector()

        assert d1 is d2

    def test_module_detect_gpu(self) -> None:
        """Module-level detect_gpu() works."""
        result = detect_gpu()
        assert isinstance(result, GPUInfo)


class TestGPUVendor:
    """Tests for GPUVendor enum."""

    def test_vendor_values(self) -> None:
        """Vendor enum has expected values."""
        assert GPUVendor.NVIDIA.value == "nvidia"
        assert GPUVendor.AMD.value == "amd"
        assert GPUVendor.INTEL.value == "intel"
        assert GPUVendor.APPLE.value == "apple"
        assert GPUVendor.UNKNOWN.value == "unknown"
        assert GPUVendor.NONE.value == "none"
