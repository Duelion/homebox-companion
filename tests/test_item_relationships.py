"""Item PUT payloads keep containment and explicit location independent."""

from unittest.mock import AsyncMock

import httpx
import pytest

from homebox_companion.core.config import Settings
from homebox_companion.homebox.models import Item, ItemUpdate
from homebox_companion.homebox.relationships import item_relationship_payload
from homebox_companion.mcp.tools import UpdateItemTool
from server.app import create_app
from server.dependencies import get_gateway

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, {"parentId": "container", "locationId": "other-location"}),
        ({"parent_id": "container"}, {"parentId": "container", "locationId": "other-location"}),
        (
            {"parent_id": "container", "location_id": "new-location"},
            {"parentId": "container", "locationId": "other-location"},
        ),
        ({"parent_id": "new-container"}, {"parentId": "new-container"}),
        ({"location_id": "new-location"}, {"parentId": "new-location"}),
        ({"clear_parent": True}, {"parentId": None}),
        (
            {"parent_id": "new-container", "location_id": "new-location", "clear_parent": True},
            {"parentId": None},
        ),
        (
            {"parent_id": "new-container", "location_id": "new-location"},
            {"parentId": "new-container"},
        ),
        ({"parent_id": None, "location_id": None}, {"parentId": "container", "locationId": "other-location"}),
    ],
)
def test_explicit_override_survives_only_unchanged_parent(changes, expected):
    current = {"parent": {"id": "container"}, "locationId": "other-location", "location": {"id": "resolved"}}
    assert item_relationship_payload(current, **changes) == expected


@pytest.mark.parametrize("parent", [None, {}])
def test_missing_parent_and_inherited_location_do_not_use_resolved_location(parent):
    current = {"parent": parent, "location": {"id": "resolved"}, "locationId": None}
    assert item_relationship_payload(current) == {"parentId": None}


def test_typed_models_distinguish_unset_and_null_location_override():
    item = Item.model_validate({"id": "item", "name": "Item", "locationId": "explicit"})
    assert item.location_id == "explicit"
    assert ItemUpdate().model_dump(by_alias=True, exclude_unset=True) == {}
    assert ItemUpdate(location_id=None).model_dump(by_alias=True, exclude_unset=True) == {"locationId": None}
    assert ItemUpdate(locationId="explicit").model_dump(by_alias=True, exclude_unset=True) == {"locationId": "explicit"}


@pytest.mark.asyncio
async def test_mcp_update_preserves_override_then_clears_on_move():
    client = AsyncMock()
    client.get_item.return_value = {
        "id": "item",
        "name": "Item",
        "parent": {"id": "container"},
        "locationId": "other-location",
        "location": {"id": "resolved"},
    }
    client.update_item.return_value = {"id": "item", "name": "Item"}
    tool = UpdateItemTool()

    await tool.execute(client, "token", tool.Params(item_id="item", notes="New note"))
    assert client.update_item.await_args.args[2]["locationId"] == "other-location"
    await tool.execute(client, "token", tool.Params(item_id="item", parent_id="new-container"))
    assert "locationId" not in client.update_item.await_args.args[2]
    assert client.update_item.await_args.args[2]["parentId"] == "new-container"
    assert client.get_item.await_count == 2


@pytest.mark.asyncio
async def test_http_update_preserves_override_without_a_move_request():
    gateway = AsyncMock()
    gateway.get_item.return_value = {
        "id": "item",
        "name": "Item",
        "parent": {"id": "container"},
        "locationId": "other-location",
        "location": {"id": "resolved"},
    }
    gateway.update_item.return_value = {"id": "item", "name": "Item"}
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.put("/api/items/item", json={"assetId": "ABC"})
        assert response.status_code == 200
        assert gateway.update_item.await_args.args[1]["locationId"] == "other-location"
        assert gateway.update_item.await_args.args[1]["parentId"] == "container"
        gateway.get_item.assert_awaited_once_with("item")


@pytest.mark.asyncio
async def test_scan_enrichment_preserves_created_parent_and_explicit_override(monkeypatch):
    from server.api import items as items_api

    gateway = AsyncMock()
    gateway.create_item.return_value = {"id": "item", "name": "Item"}
    gateway.get_item.return_value = {
        "id": "item",
        "name": "Item",
        "quantity": 1,
        "parent": {"id": "container"},
        "locationId": "explicit-location",
        "location": {"id": "resolved-location"},
    }
    gateway.update_item.return_value = {"id": "item", "name": "Item"}
    gateway.ensure_asset_ids.return_value = 0
    monkeypatch.setattr(items_api, "get_valid_tag_ids", AsyncMock(return_value=set()))
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.post(
            "/api/items",
            json={"items": [{"name": "Item", "parent_id": "container", "manufacturer": "Example"}]},
        )
    assert response.status_code == 200
    assert gateway.update_item.await_args.args[1]["parentId"] == "container"
    assert gateway.update_item.await_args.args[1]["locationId"] == "explicit-location"
    gateway.get_item.assert_awaited_once_with("item")
