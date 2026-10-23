"""Verify item containment and data retention after real MCP and companion HTTP updates."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from conftest import HomeboxAuth, HomeboxTestAccount, homebox_at_least
from pydantic import ValidationError

from homebox_companion import HomeboxClient, ItemCreate
from homebox_companion.core.config import Settings
from homebox_companion.mcp.tools import (
    GetItemByAssetIdTool,
    GetItemTool,
    ListItemsTool,
    SearchItemsTool,
    UpdateItemTool,
    UpdateLocationTool,
)
from server.app import create_app
from server.dependencies import get_gateway

pytestmark = pytest.mark.live

# First Homebox version with explicit location overrides and a resolved ``location``.
OVERRIDES = "0.27.0"


@pytest.fixture
def homebox_api_url(homebox_test_account: HomeboxTestAccount) -> str:
    return homebox_test_account.api_url


@pytest.fixture
def homebox_credentials(homebox_test_account: HomeboxTestAccount) -> tuple[str, str]:
    return homebox_test_account.email, homebox_test_account.password


async def _fresh_item(account: HomeboxTestAccount, auth: HomeboxAuth, item_id: str) -> dict[str, Any]:
    """Read through a new transport, independently of the tested client and PUT response."""
    async with httpx.AsyncClient(timeout=15, trust_env=False) as verifier:
        response = await verifier.get(
            f"{account.api_url}/entities/{item_id}",
            headers={"Authorization": f"Bearer {auth.token}"},
        )
    assert response.status_code == 200
    return response.json()


async def _nearest_location_id(account: HomeboxTestAccount, auth: HomeboxAuth, item_id: str) -> str | None:
    """Walk typed parents to the first location, as Homebox resolves inherited locations."""
    item = await _fresh_item(account, auth, item_id)
    while (parent := item.get("parent")) is not None:
        if parent["entityType"]["isLocation"]:
            return parent["id"]
        item = await _fresh_item(account, auth, parent["id"])
    return None


async def _assert_physical_location(
    account: HomeboxTestAccount,
    auth: HomeboxAuth,
    homebox_version: str,
    item_id: str,
    expected_location_id: str,
) -> None:
    """Check the resolved location in 0.27 and the nearest location ancestor in 0.26."""
    if homebox_at_least(homebox_version, OVERRIDES):
        item = await _fresh_item(account, auth, item_id)
        assert item["location"]["id"] == expected_location_id
        return
    assert await _nearest_location_id(account, auth, item_id) == expected_location_id


@asynccontextmanager
async def _companion(homebox_client: HomeboxClient, auth: HomeboxAuth) -> AsyncIterator[httpx.AsyncClient]:
    """Serve the companion item routes through a gateway backed by the real upstream client."""
    token = auth.token

    class Gateway:
        async def list_tags(self) -> list[dict[str, Any]]:
            return await homebox_client.list_tags(token)

        async def create_item(self, item: ItemCreate) -> dict[str, Any]:
            return await homebox_client.create_item(token, item)

        async def get_item(self, requested_id: str) -> dict[str, Any]:
            return await homebox_client.get_item(token, requested_id)

        async def update_item(self, requested_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            return await homebox_client.update_item(token, requested_id, payload)

        async def delete_item(self, requested_id: str) -> None:
            await homebox_client.delete_item(token, requested_id)

        async def ensure_asset_ids(self) -> int:
            return await homebox_client.ensure_asset_ids(token)

    gateway = Gateway()
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://companion.test") as client:
        yield client


async def _http_edit(
    homebox_client: HomeboxClient,
    auth: HomeboxAuth,
    item_id: str,
    body: dict[str, Any] | None = None,
) -> None:
    async with _companion(homebox_client, auth) as client:
        response = await client.put(f"/api/items/{item_id}", json=body or {"description": "HTTP ordinary edit"})
    assert response.status_code == 200


async def _create_item(
    client: HomeboxClient,
    auth: HomeboxAuth,
    cleanup_items: list[str],
    name: str,
    parent_id: str,
) -> dict[str, Any]:
    item = await client.create_item(auth.token, ItemCreate(name=name, parent_id=parent_id))
    cleanup_items.append(item["id"])
    return item


async def _set_override(client: HomeboxClient, auth: HomeboxAuth, item: dict[str, Any], parent_id: str, loc: str):
    await client.update_item(
        auth.token, item["id"], {"name": item["name"], "quantity": 1, "parentId": parent_id, "locationId": loc}
    )


@pytest.mark.asyncio
async def test_inherited_location_follows_container_after_mcp_and_http_edits(
    homebox_version: str,
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    token = homebox_auth.token
    first = await homebox_client.create_location(token, "Relationship location A")
    second = await homebox_client.create_location(token, "Relationship location B")
    cleanup_locations.extend((first["id"], second["id"]))
    container = await _create_item(homebox_client, homebox_auth, cleanup_items, "Relationship container", first["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Inherited child", container["id"])

    before = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert before["parent"]["id"] == container["id"]
    assert before.get("locationId") is None
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], first["id"])

    tool = UpdateItemTool()
    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], notes="MCP ordinary edit"))
    after_mcp = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert after_mcp["parent"]["id"] == container["id"]
    assert after_mcp.get("locationId") is None
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], first["id"])

    await tool.execute(homebox_client, token, tool.Params(item_id=container["id"], location_id=second["id"]))
    after_container_move = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert after_container_move["parent"]["id"] == container["id"]
    assert after_container_move.get("locationId") is None
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], second["id"])

    await _http_edit(homebox_client, homebox_auth, child["id"])
    after_http = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert after_http["parent"]["id"] == container["id"]
    assert after_http.get("locationId") is None
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], second["id"])


@pytest.mark.asyncio
async def test_edits_keep_every_existing_field(
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    """Homebox PUT replaces the whole item; companion edits must send everything back."""
    token = homebox_auth.token
    location = await homebox_client.create_location(token, "Retention location")
    cleanup_locations.append(location["id"])
    item = await _create_item(homebox_client, homebox_auth, cleanup_items, "Retention drill", location["id"])
    rich = {
        "name": item["name"],
        "quantity": 2,
        "parentId": location["id"],
        "description": "Cordless",
        "serialNumber": "SN-RETAIN",
        "modelNumber": "DR-9",
        "manufacturer": "Acme",
        "notes": "Charger in drawer",
        "purchaseFrom": "Shop",
        "purchasePrice": 99.5,
        "purchaseDate": "2024-05-06",
        "warrantyExpires": "2030-01-01",
        "warrantyDetails": "Full cover",
        "lifetimeWarranty": True,
        "syncChildEntityLocations": True,
        "fields": [{"type": "text", "name": "Voltage", "textValue": "18V"}],
    }
    await homebox_client.update_item(token, item["id"], rich)
    expected = {key: value for key, value in rich.items() if key not in ("name", "parentId", "fields")}

    def kept(current: dict[str, Any]) -> dict[str, Any]:
        return {key: current.get(key) for key in expected}

    def fields(current: dict[str, Any]) -> list[tuple[str, str]]:
        return [(field["name"], field["textValue"]) for field in current["fields"]]

    tool = UpdateItemTool()
    await tool.execute(homebox_client, token, tool.Params(item_id=item["id"], name="Retention hammer drill"))
    after_mcp = await _fresh_item(homebox_test_account, homebox_auth, item["id"])
    assert after_mcp["name"] == "Retention hammer drill"
    assert kept(after_mcp) == expected
    assert fields(after_mcp) == [("Voltage", "18V")]

    await _http_edit(homebox_client, homebox_auth, item["id"], {"assetId": "000-777"})
    after_http = await _fresh_item(homebox_test_account, homebox_auth, item["id"])
    assert after_http["assetId"] == "000-777"
    assert kept(after_http) == expected
    assert fields(after_http) == [("Voltage", "18V")]


@pytest.mark.asyncio
async def test_scan_create_then_asset_id_keeps_details_and_placement(
    homebox_version: str,
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    """Mirror the web scan flow: create under a picked parent, then set a custom asset ID."""
    token = homebox_auth.token
    garage = await homebox_client.create_location(token, "Scan garage")
    basement = await homebox_client.create_location(token, "Scan basement")
    cleanup_locations.extend((garage["id"], basement["id"]))
    box = await _create_item(homebox_client, homebox_auth, cleanup_items, "Scan box", garage["id"])
    overrides = homebox_at_least(homebox_version, OVERRIDES)
    if overrides:
        # The box sits on a shelf in the basement but is stored in the garage, so the
        # garage's item picker offers it even though its parent chain leads elsewhere.
        shelf = await _create_item(homebox_client, homebox_auth, cleanup_items, "Scan shelf", basement["id"])
        await _set_override(homebox_client, homebox_auth, box, shelf["id"], garage["id"])

    async with _companion(homebox_client, homebox_auth) as client:
        created = await client.post(
            "/api/items",
            json={
                "location_id": garage["id"],
                "items": [
                    {
                        "name": "Scan hammer",
                        "parent_id": box["id"],
                        "manufacturer": "Acme",
                        "serial_number": "SN-SCAN",
                        "custom_fields": {"Weight": "1kg"},
                    }
                ],
            },
        )
        assert created.status_code == 200
        [result] = created.json()["created"]
        cleanup_items.append(result["id"])
        updated = await client.put(f"/api/items/{result['id']}", json={"assetId": "000-888"})
        assert updated.status_code == 200

    hammer = await _fresh_item(homebox_test_account, homebox_auth, result["id"])
    assert hammer["parent"]["id"] == box["id"]
    assert hammer["assetId"] == "000-888"
    assert hammer["manufacturer"] == "Acme"
    assert hammer["serialNumber"] == "SN-SCAN"
    assert [(field["name"], field["textValue"]) for field in hammer["fields"]] == [("Weight", "1kg")]
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, result["id"], garage["id"])
    if overrides:
        assert hammer["locationId"] == garage["id"]


@pytest.mark.asyncio
async def test_scan_under_box_in_selected_location_keeps_inheriting(
    homebox_version: str,
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    token = homebox_auth.token
    garage = await homebox_client.create_location(token, "Inherit garage")
    cleanup_locations.append(garage["id"])
    box = await _create_item(homebox_client, homebox_auth, cleanup_items, "Inherit box", garage["id"])

    async with _companion(homebox_client, homebox_auth) as client:
        created = await client.post(
            "/api/items",
            json={"location_id": garage["id"], "items": [{"name": "Inherit nail", "parent_id": box["id"]}]},
        )
    assert created.status_code == 200
    [result] = created.json()["created"]
    cleanup_items.append(result["id"])

    nail = await _fresh_item(homebox_test_account, homebox_auth, result["id"])
    assert nail["parent"]["id"] == box["id"]
    assert nail.get("locationId") is None
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, result["id"], garage["id"])


@pytest.mark.asyncio
async def test_summary_tools_classify_parents_from_real_list_responses(
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    token = homebox_auth.token
    location = await homebox_client.create_location(token, "Summary location")
    cleanup_locations.append(location["id"])
    container = await _create_item(homebox_client, homebox_auth, cleanup_items, "Summarycontainer", location["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Summarychild", container["id"])

    search = SearchItemsTool()
    searched = await search.execute(homebox_client, token, search.Params(query="Summarycontainer"))
    [direct] = [item for item in searched.data["items"] if item["id"] == container["id"]]
    assert direct["location"]["id"] == location["id"]
    assert direct["parent"] is None

    searched = await search.execute(homebox_client, token, search.Params(query="Summarychild"))
    [nested] = [item for item in searched.data["items"] if item["id"] == child["id"]]
    assert nested["parent"]["id"] == container["id"]
    assert nested["location"] is None

    listing = ListItemsTool()
    listed = await listing.execute(homebox_client, token, listing.Params(location_id=location["id"]))
    by_id = {item["id"]: item for item in listed.data["items"]}
    assert by_id[container["id"]]["location"]["id"] == location["id"]
    assert by_id[container["id"]]["parent"] is None
    # Location filters are not recursive: items inside containers there are not returned.
    assert child["id"] not in by_id


@pytest.mark.asyncio
async def test_detail_tools_report_container_and_location(
    homebox_version: str,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    token = homebox_auth.token
    location = await homebox_client.create_location(token, "Detail location")
    cleanup_locations.append(location["id"])
    container = await _create_item(homebox_client, homebox_auth, cleanup_items, "Detail container", location["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Detail child", container["id"])
    await homebox_client.ensure_asset_ids(token)
    by_id = GetItemTool()
    by_asset = GetItemByAssetIdTool()
    # 0.26 details have no resolved location for items nested in another item.
    nested_location = location["id"] if homebox_at_least(homebox_version, OVERRIDES) else None

    for item, expected_parent, expected_location in (
        (container, None, location["id"]),
        (child, container["id"], nested_location),
    ):
        asset_id = (await homebox_client.get_item(token, item["id"]))["assetId"]
        assert asset_id
        results = (
            await by_id.execute(homebox_client, token, by_id.Params(item_id=item["id"])),
            await by_asset.execute(homebox_client, token, by_asset.Params(asset_id=asset_id)),
        )
        for result in results:
            assert result.data["id"] == item["id"]
            assert (result.data["parent"] or {}).get("id") == expected_parent
            assert (result.data["location"] or {}).get("id") == expected_location


@pytest.mark.asyncio
async def test_location_filter_reports_overridden_nested_item_there(
    homebox_version: str,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    if not homebox_at_least(homebox_version, OVERRIDES):
        pytest.skip("Explicit location overrides require Homebox 0.27.0")

    token = homebox_auth.token
    first = await homebox_client.create_location(token, "Filter location A")
    second = await homebox_client.create_location(token, "Filter location B")
    cleanup_locations.extend((first["id"], second["id"]))
    container = await _create_item(homebox_client, homebox_auth, cleanup_items, "Filter container", first["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Filter child", container["id"])
    sibling = await _create_item(homebox_client, homebox_auth, cleanup_items, "Filter sibling", container["id"])
    await _set_override(homebox_client, homebox_auth, child, container["id"], second["id"])

    listing = ListItemsTool()
    at_second = await listing.execute(homebox_client, token, listing.Params(location_id=second["id"]))
    second_ids = {item["id"] for item in at_second.data["items"]}
    [nested] = [item for item in at_second.data["items"] if item["id"] == child["id"]]
    assert nested["parent"]["id"] == container["id"]
    assert nested["location"]["id"] == second["id"]

    at_first = await listing.execute(homebox_client, token, listing.Params(location_id=first["id"]))
    first_ids = {item["id"] for item in at_first.data["items"]}
    assert container["id"] in first_ids
    # Only direct children and override matches are returned; inheriting nested items never are.
    assert sibling["id"] not in first_ids | second_ids
    assert child["id"] not in first_ids


@pytest.mark.asyncio
async def test_mcp_intentional_moves(
    homebox_version: str,
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    token = homebox_auth.token
    first = await homebox_client.create_location(token, "Move location A")
    second = await homebox_client.create_location(token, "Move location B")
    cleanup_locations.extend((first["id"], second["id"]))
    container = await _create_item(homebox_client, homebox_auth, cleanup_items, "Move container", first["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Move child", first["id"])
    tool = UpdateItemTool()

    with pytest.raises(ValidationError, match="Pass only one of parent_id, location_id or clear_parent"):
        tool.Params(item_id=child["id"], parent_id=container["id"], location_id=second["id"])

    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], parent_id=container["id"]))
    under_container = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert under_container["parent"]["id"] == container["id"]
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], first["id"])

    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], location_id=second["id"]))
    at_second = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert at_second["parent"]["id"] == second["id"]
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], second["id"])

    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], clear_parent=True))
    top_level = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert top_level.get("parent") is None
    assert top_level.get("locationId") is None


@pytest.mark.asyncio
async def test_explicit_location_override_survives_edits_and_clears_on_parent_change(
    homebox_version: str,
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    if not homebox_at_least(homebox_version, OVERRIDES):
        pytest.skip("Explicit location overrides require Homebox 0.27.0")

    token = homebox_auth.token
    first = await homebox_client.create_location(token, "Override location A")
    second = await homebox_client.create_location(token, "Override location B")
    cleanup_locations.extend((first["id"], second["id"]))
    container = await _create_item(homebox_client, homebox_auth, cleanup_items, "Override container", first["id"])
    other = await _create_item(homebox_client, homebox_auth, cleanup_items, "Override other container", first["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Override child", container["id"])

    await _set_override(homebox_client, homebox_auth, child, container["id"], second["id"])
    overridden = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert overridden["parent"]["id"] == container["id"]
    assert overridden["locationId"] == second["id"]
    assert overridden["location"]["id"] == second["id"]

    tool = UpdateItemTool()
    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], notes="Keep override"))
    after_mcp = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert after_mcp["locationId"] == second["id"]
    assert after_mcp["parent"]["id"] == container["id"]
    assert after_mcp["location"]["id"] == second["id"]

    await _http_edit(homebox_client, homebox_auth, child["id"])
    after_http = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert after_http["locationId"] == second["id"]
    assert after_http["parent"]["id"] == container["id"]
    assert after_http["location"]["id"] == second["id"]

    # Switching containers drops the override; the item follows its new container.
    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], parent_id=other["id"]))
    switched = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert switched["parent"]["id"] == other["id"]
    assert switched.get("locationId") is None
    assert switched["location"]["id"] == first["id"]

    await _set_override(homebox_client, homebox_auth, child, container["id"], second["id"])
    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], clear_parent=True))
    cleared = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert cleared.get("parent") is None
    assert cleared.get("locationId") is None
    assert cleared.get("location") is None

    await _set_override(homebox_client, homebox_auth, child, container["id"], second["id"])
    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], location_id=first["id"]))
    moved = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert moved["parent"]["id"] == first["id"]
    assert moved.get("locationId") is None
    assert moved["location"]["id"] == first["id"]


@pytest.mark.asyncio
async def test_location_rename_keeps_existing_fields(
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_locations: list[str],
) -> None:
    """Locations are entities, so a rename must not reset the rest of the entity."""
    token = homebox_auth.token
    house = await homebox_client.create_location(token, "Rename house")
    garage = await homebox_client.create_location(token, "Rename garage", parent_id=house["id"])
    cleanup_locations.extend((garage["id"], house["id"]))
    await homebox_client.update_item(
        token,
        garage["id"],
        {
            "name": garage["name"],
            "parentId": house["id"],
            "description": "Detached",
            "notes": "Key under the mat",
            "fields": [{"type": "text", "name": "Code", "textValue": "1234"}],
        },
    )

    tool = UpdateLocationTool()
    await tool.execute(homebox_client, token, tool.Params(location_id=garage["id"], name="Rename workshop"))

    renamed = await _fresh_item(homebox_test_account, homebox_auth, garage["id"])
    assert renamed["name"] == "Rename workshop"
    assert renamed["description"] == "Detached"
    assert renamed["notes"] == "Key under the mat"
    assert [(field["name"], field["textValue"]) for field in renamed["fields"]] == [("Code", "1234")]
    assert renamed["parent"]["id"] == house["id"]


@pytest.mark.asyncio
async def test_detail_custom_fields_survive_unrelated_edit(
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    """Both detail tools expose official fields in the version/auth fixture matrix."""
    token = homebox_auth.token
    location = await homebox_client.create_location(token, "Custom field detail location")
    cleanup_locations.append(location["id"])
    item = await _create_item(homebox_client, homebox_auth, cleanup_items, "Custom field detail", location["id"])
    fields = [
        {"type": "text", "name": "QA Material 材料", "textValue": "木材"},
        {"type": "text", "name": "Duplicate", "textValue": ""},
        {"type": "number", "name": "Duplicate", "numberValue": 0},
        {"type": "boolean", "name": "Enabled", "booleanValue": False},
    ]
    await homebox_client.update_item(
        token, item["id"], {"name": item["name"], "quantity": 1, "parentId": location["id"], "fields": fields}
    )
    await homebox_client.ensure_asset_ids(token)
    official = await _fresh_item(homebox_test_account, homebox_auth, item["id"])

    def values(entries):
        return [
            {key: entry.get(key) for key in ("name", "type", "textValue", "numberValue", "booleanValue")}
            for entry in entries
        ]

    results = [
        await GetItemTool().execute(homebox_client, token, GetItemTool.Params(item_id=item["id"])),
        await GetItemByAssetIdTool().execute(
            homebox_client, token, GetItemByAssetIdTool.Params(asset_id=official["assetId"])
        ),
    ]
    for result in results:
        assert result.success
        assert values(result.data["fields"]) == values(official["fields"])
        for expected in fields:
            assert any(all(entry[key] == value for key, value in expected.items()) for entry in result.data["fields"])
    update = UpdateItemTool()
    await update.execute(homebox_client, token, update.Params(item_id=item["id"], notes="Unrelated custom-field edit"))
    await _http_edit(homebox_client, homebox_auth, item["id"])
    fresh = await _fresh_item(homebox_test_account, homebox_auth, item["id"])
    assert fresh["fields"] == official["fields"]


@pytest.mark.asyncio
async def test_explicit_override_controls_match_reported_homebox_version(
    homebox_version: str,
    homebox_test_account: HomeboxTestAccount,
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    token = homebox_auth.token
    first = await homebox_client.create_location(token, "Explicit control chain location")
    other = await homebox_client.create_location(token, "Explicit control physical location")
    cleanup_locations.extend((first["id"], other["id"]))
    parent = await _create_item(homebox_client, homebox_auth, cleanup_items, "Explicit control parent", first["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Explicit control child", parent["id"])
    tool = UpdateItemTool()
    params = tool.Params(item_id=child["id"], location_override_id=other["id"])
    if not homebox_at_least(homebox_version, OVERRIDES):
        with pytest.raises(ValueError, match="recognized Homebox version"):
            await tool.execute(homebox_client, token, params)
        await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], notes="ordinary 0.26 update"))
        unchanged = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
        assert unchanged["parent"]["id"] == parent["id"]
        return
    await tool.execute(homebox_client, token, params)
    overridden = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert overridden["parent"]["id"] == parent["id"]
    assert overridden["locationId"] == other["id"]
    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], clear_location_override=True))
    cleared = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert cleared["parent"]["id"] == parent["id"]
    assert cleared.get("locationId") is None
    assert cleared["location"]["id"] == first["id"]
