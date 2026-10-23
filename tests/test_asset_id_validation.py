"""Asset ID validation follows the supported Homebox JSON contract."""

from unittest.mock import AsyncMock

import httpx
import pytest

from homebox_companion import HomeboxClient
from homebox_companion.core.config import Settings
from homebox_companion.homebox.asset_id import normalize_asset_id
from server.app import create_app
from server.dependencies import get_gateway


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        ("   ", ""),
        ("032-303", "032-303"),
        ("32303", "032-303"),
        (" +000032-303 ", "032-303"),
        ("0", "0"),
        ("000-000", "0"),
        ("12-34-567", "123-4567"),
        ("-001", "000-001"),
        ("9223372036854775807", "922-3372036854775807"),
    ],
)
def test_normalizes_supported_homebox_asset_ids(value, expected):
    assert normalize_asset_id(value) == expected


@pytest.mark.parametrize(
    "value", ["032-REVIEW-3", "9223372036854775808", "--", "+", "3.2", "１２３", '"123"', "12 3", 123]
)
def test_rejects_unsupported_homebox_asset_ids(value):
    with pytest.raises(ValueError, match="numeric Homebox asset ID"):
        normalize_asset_id(value)


@pytest.mark.asyncio
async def test_invalid_update_never_reads_or_mutates_homebox():
    gateway = AsyncMock()
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.put("/api/items/item", json={"assetId": "032-REVIEW-3"})
    assert response.status_code == 422
    gateway.get_item.assert_not_awaited()
    gateway.update_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_library_update_rejects_invalid_id_without_http_request():
    http = AsyncMock(spec=httpx.AsyncClient)
    client = HomeboxClient(base_url="http://homebox.test/api/v1", client=http)
    with pytest.raises(ValueError, match="numeric Homebox asset ID"):
        await client.update_item("test-token", "item", {"assetId": "032-REVIEW-3"})
    http.put.assert_not_awaited()
