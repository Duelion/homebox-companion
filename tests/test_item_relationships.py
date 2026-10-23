"""Item PUT payloads keep containment and explicit location independent."""

from unittest.mock import AsyncMock

import httpx
import pytest

from homebox_companion import HomeboxClient
from homebox_companion.core import HomeboxAPIError
from homebox_companion.core.config import Settings
from homebox_companion.core.exceptions import HomeboxConnectionError, HomeboxTimeoutError
from homebox_companion.homebox.models import Item, ItemUpdate
from homebox_companion.homebox.relationships import (
    item_relationship_payload,
    item_update_payload,
    location_override_for_parent,
)
from homebox_companion.mcp.tools import UpdateItemTool, UpdateLocationTool
from server.app import create_app
from server.dependencies import get_gateway
from server.services.duplicate_checker import DuplicateChecker

ITEM_TYPE = {"isLocation": False}

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
        response = await client.put("/api/items/item", json={"assetId": "000-123"})
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


# A detail response carrying every writable field Homebox would otherwise reset.
FULL_ITEM = {
    "id": "item",
    "name": "Drill",
    "description": "Cordless",
    "quantity": 2,
    "assetId": "000-042",
    "insured": True,
    "archived": False,
    "syncChildEntityLocations": True,
    "serialNumber": "SN-1",
    "modelNumber": "DR-9",
    "manufacturer": "Acme",
    "lifetimeWarranty": True,
    "warrantyExpires": "2030-01-01",
    "warrantyDetails": "Full cover",
    "purchaseDate": "2024-05-06",
    "purchaseFrom": "Shop",
    "purchasePrice": 99.5,
    "soldDate": "",
    "soldTo": "",
    "soldPrice": 0,
    "soldNotes": "",
    "notes": "Charger in drawer",
    "parent": {"id": "box", "name": "Box", "entityType": ITEM_TYPE},
    "location": {"id": "garage", "name": "Garage"},
    "locationId": "garage",
    "tags": [{"id": "tag-1", "name": "Tools"}],
    "fields": [
        {
            "id": "field-1",
            "type": "text",
            "name": "Voltage",
            "textValue": "18V",
            "numberValue": 0,
            "booleanValue": False,
        }
    ],
    "attachments": [{"id": "att-1"}],
    "entityType": ITEM_TYPE,
}
PRESERVED_KEYS = (
    "description",
    "quantity",
    "insured",
    "archived",
    "syncChildEntityLocations",
    "serialNumber",
    "modelNumber",
    "manufacturer",
    "lifetimeWarranty",
    "warrantyExpires",
    "warrantyDetails",
    "purchaseDate",
    "purchaseFrom",
    "purchasePrice",
    "soldDate",
    "soldTo",
    "soldPrice",
    "soldNotes",
    "notes",
    "fields",
)
PRESERVED = {key: FULL_ITEM[key] for key in PRESERVED_KEYS}


def test_update_payload_round_trips_every_writable_field():
    assert item_update_payload(FULL_ITEM) == {
        **PRESERVED,
        "id": "item",
        "name": "Drill",
        "assetId": "000-042",
        "tagIds": ["tag-1"],
        "parentId": "box",
        "locationId": "garage",
    }


@pytest.mark.asyncio
async def test_asset_id_update_keeps_every_existing_field():
    gateway = AsyncMock()
    gateway.get_item.return_value = FULL_ITEM
    gateway.update_item.return_value = {"id": "item"}
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.put("/api/items/item", json={"assetId": "000-100"})

    assert response.status_code == 200
    payload = gateway.update_item.await_args.args[1]
    assert payload["assetId"] == "000-100"
    assert {key: payload[key] for key in PRESERVED_KEYS} == PRESERVED


@pytest.mark.asyncio
async def test_mcp_update_keeps_every_existing_field():
    client = AsyncMock()
    client.get_item.return_value = FULL_ITEM
    client.update_item.return_value = {"id": "item", "name": "Hammer drill"}
    tool = UpdateItemTool()

    await tool.execute(client, "token", tool.Params(item_id="item", name="Hammer drill"))

    payload = client.update_item.await_args.args[2]
    assert payload["name"] == "Hammer drill"
    assert payload["tagIds"] == ["tag-1"]
    assert {key: payload[key] for key in PRESERVED_KEYS} == PRESERVED


async def _create(monkeypatch, body: dict, parent: dict | Exception | None = None) -> AsyncMock:
    from server.api import items as items_api

    gateway = AsyncMock()
    gateway.create_item.return_value = {"id": "item", "name": "Item"}
    if isinstance(parent, Exception):
        gateway.get_item.side_effect = parent
    elif parent is not None:
        gateway.get_item.return_value = parent
    gateway.ensure_asset_ids.return_value = 0
    monkeypatch.setattr(items_api, "get_valid_tag_ids", AsyncMock(return_value=set()))
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/api/items", json=body)
    assert response.status_code == 200
    return gateway


def _create_payloads(gateway: AsyncMock) -> list[dict]:
    return [call.args[0].model_dump(by_alias=True, exclude_unset=True) for call in gateway.create_item.await_args_list]


@pytest.mark.parametrize(
    ("parent", "expected"),
    [
        ({"entityType": ITEM_TYPE, "locationId": "garage"}, "garage"),
        ({"entityType": ITEM_TYPE, "location": {"id": "garage"}}, None),
        ({"entityType": ITEM_TYPE}, None),
        ({"locationId": "garage"}, None),
        ({"entityType": {"isLocation": True}, "locationId": "garage"}, None),
    ],
)
def test_location_override_only_for_parents_with_their_own_override(parent, expected):
    assert location_override_for_parent(parent, "garage") == expected


@pytest.mark.asyncio
async def test_scan_under_overridden_parent_keeps_selected_location(monkeypatch):
    """0.27 children inherit through the parent chain, not the parent's own override."""
    parent = {"id": "box", "entityType": ITEM_TYPE, "parent": {"id": "shelf"}, "locationId": "garage"}
    gateway = await _create(
        monkeypatch,
        {"items": [{"name": "A", "parent_id": "box"}, {"name": "B", "parent_id": "box"}], "location_id": "garage"},
        parent,
    )

    payloads = _create_payloads(gateway)
    assert [p["parentId"] for p in payloads] == ["box", "box"]
    assert [p["locationId"] for p in payloads] == ["garage", "garage"]
    gateway.get_item.assert_awaited_once_with("box")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "parent", "expected_parent", "reads_parent"),
    [
        # A parent placed in the location passes it on; pinning would stop the child following it.
        (
            {"items": [{"name": "A", "parent_id": "box"}], "location_id": "garage"},
            {"id": "box", "entityType": ITEM_TYPE, "parent": {"id": "garage"}, "location": {"id": "garage"}},
            "box",
            True,
        ),
        # 0.26 details carry no locationId.
        (
            {"items": [{"name": "A", "parent_id": "box"}], "location_id": "garage"},
            {"id": "box", "entityType": ITEM_TYPE, "parent": {"id": "garage"}},
            "box",
            True,
        ),
        ({"items": [{"name": "A"}], "location_id": "garage"}, None, "garage", False),
        ({"items": [{"name": "A", "parent_id": "box"}]}, None, "box", False),
    ],
)
async def test_scan_create_inherits_without_override(monkeypatch, body, parent, expected_parent, reads_parent):
    gateway = await _create(monkeypatch, body, parent)

    [payload] = _create_payloads(gateway)
    assert payload["parentId"] == expected_parent
    assert "locationId" not in payload
    assert gateway.get_item.await_count == (1 if reads_parent else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [HomeboxAPIError("boom"), HomeboxTimeoutError("slow"), HomeboxConnectionError("down")]
)
async def test_unreadable_parent_still_creates_item_under_it(monkeypatch, error):
    gateway = await _create(monkeypatch, {"items": [{"name": "A", "parent_id": "box"}], "location_id": "garage"}, error)

    [payload] = _create_payloads(gateway)
    assert payload["parentId"] == "box"
    assert "locationId" not in payload


@pytest.mark.asyncio
async def test_duplicate_match_reports_physical_location_not_container():
    gateway = AsyncMock()
    gateway.list_items.return_value = {"items": [{"id": "drill"}]}
    gateway.get_item.return_value = {
        "id": "drill",
        "name": "Drill",
        "serialNumber": "SN1",
        "parent": {"id": "toolchest", "name": "Toolchest", "entityType": ITEM_TYPE},
        "location": {"id": "workshop", "name": "Workshop"},
    }

    match = await DuplicateChecker(gateway).check_serial_number("sn1")

    assert match is not None and match.location_name == "Workshop"


LOCATION = {
    "id": "garage",
    "name": "Garage",
    "description": "Detached",
    "notes": "Key under the mat",
    "insured": True,
    "parent": {"id": "house", "name": "House", "entityType": {"isLocation": True}},
    "tags": [{"id": "tag-1"}],
    "fields": [{"id": "field-1", "type": "text", "name": "Code", "textValue": "1234"}],
    "entityType": {"isLocation": True},
}


@pytest.mark.asyncio
@pytest.mark.parametrize(("parent_id", "expected_parent"), [("house", "house"), (None, None), ("", None)])
async def test_location_update_keeps_existing_entity_fields(parent_id, expected_parent):
    puts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=LOCATION)
        puts.append(request)
        return httpx.Response(200, json={"id": "garage"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HomeboxClient(base_url="http://homebox.test/api/v1", client=http_client)
        await client.update_location("token", "garage", name="Workshop", description="", parent_id=parent_id)

    [put] = puts
    assert put.url.path == "/api/v1/entities/garage"
    body = httpx.Response(200, content=put.content).json()
    assert body["name"] == "Workshop"
    assert body["description"] == ""
    assert body["parentId"] == expected_parent
    assert body["notes"] == "Key under the mat"
    assert body["insured"] is True
    assert body["tagIds"] == ["tag-1"]
    assert body["fields"] == LOCATION["fields"]


@pytest.mark.asyncio
async def test_update_location_tool_handles_top_level_location():
    client = AsyncMock()
    client.get_location.return_value = {"id": "garage", "name": "Garage", "parent": None}
    client.update_location.return_value = {"id": "garage", "name": "Shed"}
    tool = UpdateLocationTool()

    result = await tool.execute(client, "token", tool.Params(location_id="garage", name="Shed"))

    assert result.success is True
    assert client.update_location.await_args.kwargs["parent_id"] is None
