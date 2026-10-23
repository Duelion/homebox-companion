"""Untrusted image uploads are decoded before any AI call."""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image

from homebox_companion.ai.images import encode_image_bytes_to_data_uri, validate_image_bytes
from homebox_companion.core.config import Settings
from server.api.tools import vision
from server.dependencies import get_vision_context, require_llm_configured


def photo(fmt="JPEG"):
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format=fmt)
    return output.getvalue()


@pytest.mark.parametrize(
    "fmt,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp"), ("GIF", "image/gif")]
)
def test_actual_decoded_format_is_authoritative(fmt, mime):
    contents = photo(fmt)
    assert validate_image_bytes(contents) == mime
    assert encode_image_bytes_to_data_uri(contents, "text/plain", optimize=False).startswith(f"data:{mime};")


@pytest.mark.parametrize(
    "contents",
    [b"", b"not an image", b"\x89PNG\r\n\x1a\ncorrupt", photo()[:40], photo("BMP"), b"\x00\x00\x00\x18ftypheicjunk"],
)
def test_invalid_bytes_cannot_fall_back_to_provider(contents):
    with pytest.raises(ValueError, match="Invalid or unsupported image"):
        encode_image_bytes_to_data_uri(contents)


def test_decompression_warning_is_rejected(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 50)
    with pytest.raises(ValueError, match="Invalid or unsupported image"):
        validate_image_bytes(photo())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint,additional", [("detect", False), ("detect", True), ("analyze", False), ("correct", False)]
)
@pytest.mark.parametrize(
    "contents,expected",
    [(b"text disguised as image", 400), (b"", 400), (b"\xff\xd8\xffcorrupt", 400), (b"x" * (1024 * 1024 + 1), 413)],
    ids=["text", "empty", "corrupt", "oversize"],
)
async def test_vision_routes_reject_invalid_before_ai(endpoint, additional, contents, expected, monkeypatch):
    app = FastAPI()
    app.state.settings = Settings(max_upload_size_mb=1)
    app.include_router(vision.router)
    app.dependency_overrides[get_vision_context] = lambda: SimpleNamespace(tags=[])
    app.dependency_overrides[require_llm_configured] = lambda: "sentinel-key"
    providers = []
    for name in ("detect_items_from_bytes", "analyze_item_details_from_images", "llm_correct_item"):
        mock = AsyncMock(side_effect=AssertionError("AI must not be called"))
        monkeypatch.setattr(vision, name, mock)
        providers.append(mock)
    field = "images" if endpoint == "analyze" else "image"
    files = [(field, ("photo.jpg", photo() if additional else contents, "image/jpeg"))]
    if additional:
        files.append(("additional_images", ("extra.jpg", contents, "image/jpeg")))
    data = {"item_name": "Item", "current_item": '{"name":"Item"}', "correction_instructions": "Fix name"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.post(f"/{endpoint}", files=files, data=data)
    assert response.status_code == expected
    assert "sentinel" not in response.text
    if expected == 400 and contents:
        assert "Invalid or unsupported image" in response.json()["detail"]
    for mock in providers:
        mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP", "GIF"])
async def test_valid_upload_ignores_spoofed_mime_and_reaches_detection(fmt, monkeypatch):
    app = FastAPI()
    app.state.settings = Settings()
    app.include_router(vision.router)
    app.dependency_overrides[get_vision_context] = lambda: SimpleNamespace(
        tags=[], field_preferences=None, output_language=None, custom_fields=[], default_tag_id=None
    )
    app.dependency_overrides[require_llm_configured] = lambda: "sentinel-key"
    provider = AsyncMock(return_value=[])
    monkeypatch.setattr(vision, "detect_items_from_bytes", provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/detect", files={"image": ("wrong.txt", photo(fmt), "text/plain")})
    assert response.status_code == 200, response.text
    assert provider.await_args is not None
    assert provider.await_args.kwargs["mime_type"] == validate_image_bytes(photo(fmt))
