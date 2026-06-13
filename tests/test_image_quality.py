"""Tests for HBC_IMAGE_QUALITY enforcement.

Covers the compression primitive and the upload endpoint's compression
behaviour. The endpoint-level tests are written to fail against the current
implementation (which forwards the raw upload bytes to Homebox untouched)
and pass once HBC_IMAGE_QUALITY is enforced server-side at upload time.

Background: https://github.com/Duelion/homebox-companion/issues/135
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from homebox_companion.ai.images import compress_image_for_upload
from homebox_companion.core.config import ImageQuality, Settings

LARGE_ASSET = Path(__file__).parent / "assets" / "single_item_single_image.jpg"


def _image_dimensions(jpeg_bytes: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(jpeg_bytes)).size


class TestImageQualityParams:
    """Settings.image_quality_params should map enum values to (max_dim, jpeg_q)."""

    @pytest.mark.parametrize(
        ("quality", "expected"),
        [
            (ImageQuality.RAW, (None, 100)),
            (ImageQuality.HIGH, (2560, 85)),
            (ImageQuality.MEDIUM, (1920, 75)),
            (ImageQuality.LOW, (1280, 60)),
        ],
    )
    def test_mapping(self, quality: ImageQuality, expected: tuple[int | None, int]) -> None:
        s = Settings(image_quality=quality, llm_api_key="sk-test")
        assert s.image_quality_params == expected


class TestCompressImageForUpload:
    """compress_image_for_upload should resize+recompress per quality settings."""

    @pytest.fixture
    def large_jpeg(self) -> bytes:
        return LARGE_ASSET.read_bytes()

    def test_raw_returns_original_bytes(self, large_jpeg: bytes) -> None:
        out_bytes, mime = compress_image_for_upload(large_jpeg, max_dimension=None, quality=100)
        assert out_bytes == large_jpeg
        assert mime == "image/jpeg"

    @pytest.mark.parametrize(
        ("max_dim", "jpeg_q"),
        [(2560, 85), (1920, 75), (1280, 60)],
    )
    def test_resizes_when_larger_than_max(
        self, large_jpeg: bytes, max_dim: int, jpeg_q: int
    ) -> None:
        out_bytes, mime = compress_image_for_upload(large_jpeg, max_dimension=max_dim, quality=jpeg_q)
        w, h = _image_dimensions(out_bytes)
        assert max(w, h) == max_dim, f"expected longest side {max_dim}, got {(w, h)}"
        assert len(out_bytes) < len(large_jpeg)
        assert mime == "image/jpeg"

    def test_no_upscale_when_smaller(self) -> None:
        small = io.BytesIO()
        Image.new("RGB", (800, 600), color=(255, 0, 0)).save(small, format="JPEG", quality=90)
        original = small.getvalue()
        out_bytes, _ = compress_image_for_upload(original, max_dimension=1920, quality=75)
        w, h = _image_dimensions(out_bytes)
        assert (w, h) == (800, 600), "compression should not upscale smaller images"

class _CapturingHomeboxClient:
    """Minimal stand-in for HomeboxClient that records upload_attachment calls."""

    def __init__(self) -> None:
        self.last_file_bytes: bytes | None = None
        self.last_filename: str | None = None
        self.last_mime_type: str | None = None

    async def upload_attachment(
        self,
        token: str,
        item_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        attachment_type: str = "photo",
    ) -> dict[str, Any]:
        self.last_file_bytes = file_bytes
        self.last_filename = filename
        self.last_mime_type = mime_type
        return {"id": "fake-attachment-id", "type": attachment_type, "name": filename}


@pytest.fixture
def upload_test_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, _CapturingHomeboxClient]:
    """Build a minimal FastAPI app mounting only the items router, with overrides."""
    from server.api import items as items_module
    from server.dependencies import get_client, get_token

    capture = _CapturingHomeboxClient()
    app = FastAPI()
    app.include_router(items_module.router)
    app.dependency_overrides[get_client] = lambda: capture
    app.dependency_overrides[get_token] = lambda: "fake-token"
    return TestClient(app), capture


@pytest.mark.parametrize(
    ("quality", "max_dim"),
    [
        (ImageQuality.LOW, 1280),
        (ImageQuality.MEDIUM, 1920),
        (ImageQuality.HIGH, 2560),
    ],
)
def test_upload_endpoint_compresses_per_image_quality(
    monkeypatch: pytest.MonkeyPatch,
    upload_test_client: tuple[TestClient, _CapturingHomeboxClient],
    quality: ImageQuality,
    max_dim: int,
) -> None:
    """Posting a 4032x3024 image with HBC_IMAGE_QUALITY=X must forward a resized image."""
    from server.api import items as items_module

    monkeypatch.setattr(items_module.settings, "image_quality", quality)

    client, capture = upload_test_client
    original = LARGE_ASSET.read_bytes()

    response = client.post(
        "/items/some-item-id/attachments",
        files={"file": ("photo.jpg", original, "image/jpeg")},
    )

    assert response.status_code == 200, response.text
    assert capture.last_file_bytes is not None, "Homebox client was not called"

    forwarded = capture.last_file_bytes
    assert forwarded != original, (
        "Endpoint forwarded the original bytes — HBC_IMAGE_QUALITY was ignored. "
        "See issue #135."
    )

    w, h = _image_dimensions(forwarded)
    assert max(w, h) == max_dim, (
        f"Forwarded image longest side is {max(w, h)} but {quality} requires {max_dim}."
    )
    assert len(forwarded) < len(original)


def test_upload_endpoint_raw_passes_through(
    monkeypatch: pytest.MonkeyPatch,
    upload_test_client: tuple[TestClient, _CapturingHomeboxClient],
) -> None:
    """HBC_IMAGE_QUALITY=raw must forward bytes unchanged."""
    from server.api import items as items_module

    monkeypatch.setattr(items_module.settings, "image_quality", ImageQuality.RAW)

    client, capture = upload_test_client
    original = LARGE_ASSET.read_bytes()

    response = client.post(
        "/items/some-item-id/attachments",
        files={"file": ("photo.jpg", original, "image/jpeg")},
    )

    assert response.status_code == 200, response.text
    assert capture.last_file_bytes == original
