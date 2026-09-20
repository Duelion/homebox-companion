"""Keep known Homebox creations visible when later operations fail."""

from unittest.mock import AsyncMock

import httpx
import pytest

from homebox_companion import HomeboxAuthError, HomeboxClient
from homebox_companion.core.config import Settings
from server.api import items as items_api
from server.app import create_app
from server.dependencies import get_gateway

pytestmark = pytest.mark.unit


@pytest.fixture
def gateway(monkeypatch):
    # Gateway methods are dynamic delegates to this client's API surface.
    gateway = AsyncMock(spec=HomeboxClient)
    item = {"id": "created-id", "name": "Lamp", "parent": {"id": "location"}, "tags": [], "quantity": 1}
    gateway.create_item.return_value = item
    gateway.get_item.return_value = item
    gateway.update_item.return_value = item
    gateway.ensure_asset_ids.return_value = 0
    monkeypatch.setattr(items_api, "get_valid_tag_ids", AsyncMock(return_value=set()))
    return gateway


async def submit(gateway, items):
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        return await client.post("/api/items", json={"items": items, "location_id": "location"})


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["get_item", "update_item"])
async def test_post_create_auth_failure_returns_created_id_and_stops_batch(gateway, stage):
    getattr(gateway, stage).side_effect = HomeboxAuthError("Expired")
    response = await submit(
        gateway,
        [
            {"name": "Lamp", "purchase_price": 0},
            {"name": "Unattempted chair"},
            {"name": "Unattempted table"},
        ],
    )

    assert response.status_code == 207
    assert [item["id"] for item in response.json()["created"]] == ["created-id"]
    assert response.json()["errors"] == [
        "Authentication failed for 'Lamp'",
        "2 more item(s) not attempted due to auth failure",
    ]
    gateway.create_item.assert_awaited_once()
    gateway.delete_item.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_error", [RuntimeError("Unavailable"), HomeboxAuthError("Expired")])
async def test_failed_cleanup_returns_known_id_as_incomplete(gateway, cleanup_error):
    gateway.update_item.side_effect = RuntimeError("Update failed")
    gateway.delete_item.side_effect = cleanup_error

    response = await submit(gateway, [{"name": "Lamp", "manufacturer": "Example"}])

    assert response.status_code == 207
    assert response.json()["created"][0]["id"] == "created-id"
    assert response.json()["errors"]
    gateway.delete_item.assert_awaited_once_with("created-id")


@pytest.mark.asyncio
async def test_confirmed_cleanup_leaves_failure_safe_to_retry(gateway):
    gateway.update_item.side_effect = RuntimeError("Update failed")

    response = await submit(gateway, [{"name": "Lamp", "manufacturer": "Example"}])

    assert response.status_code == 207
    assert response.json()["created"] == []
    gateway.delete_item.assert_awaited_once_with("created-id")


@pytest.mark.asyncio
async def test_auth_failure_before_creation_does_not_claim_an_item_exists(gateway):
    gateway.create_item.side_effect = HomeboxAuthError("Expired")

    response = await submit(gateway, [{"name": "Lamp", "purchase_price": 0}])

    assert response.status_code == 207
    assert response.json()["created"] == []
    gateway.delete_item.assert_not_awaited()
