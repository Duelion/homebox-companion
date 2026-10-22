"""Verify item containment after real MCP and companion HTTP updates."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from conftest import HomeboxAuth, HomeboxTestAccount

from homebox_companion import HomeboxClient, ItemCreate
from homebox_companion.core.config import Settings
from homebox_companion.mcp.tools import UpdateItemTool
from server.app import create_app
from server.dependencies import get_gateway

pytestmark = pytest.mark.live


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


async def _assert_physical_location(
    account: HomeboxTestAccount,
    auth: HomeboxAuth,
    homebox_version: str,
    item_id: str,
    expected_location_id: str,
) -> None:
    """Check resolved location in 0.27 and independent containment path in 0.26."""
    if homebox_version == "0.27.0":
        item = await _fresh_item(account, auth, item_id)
        assert item["location"]["id"] == expected_location_id
        return
    async with httpx.AsyncClient(timeout=15, trust_env=False) as verifier:
        response = await verifier.get(
            f"{account.api_url}/entities/{item_id}/path",
            headers={"Authorization": f"Bearer {auth.token}"},
        )
    assert response.status_code == 200
    assert expected_location_id in [ancestor["id"] for ancestor in response.json()]


async def _http_edit(homebox_client: HomeboxClient, auth: HomeboxAuth, item_id: str) -> None:
    """Exercise the companion route with a gateway backed by the real upstream client."""

    class Gateway:
        async def get_item(self, requested_id: str) -> dict[str, Any]:
            return await homebox_client.get_item(auth.token, requested_id)

        async def update_item(self, requested_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            return await homebox_client.update_item(auth.token, requested_id, payload)

    gateway = Gateway()
    app = create_app(Settings(disable_update_check=True))
    app.dependency_overrides[get_gateway] = lambda: gateway
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://companion.test") as client:
        response = await client.put(f"/api/items/{item_id}", json={"description": "HTTP ordinary edit"})
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
async def test_mcp_intentional_moves_and_precedence(
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

    await tool.execute(
        homebox_client,
        token,
        tool.Params(item_id=child["id"], parent_id=container["id"], location_id=second["id"]),
    )
    under_container = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert under_container["parent"]["id"] == container["id"]
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], first["id"])

    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], location_id=second["id"]))
    at_second = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert at_second["parent"]["id"] == second["id"]
    await _assert_physical_location(homebox_test_account, homebox_auth, homebox_version, child["id"], second["id"])

    await tool.execute(
        homebox_client,
        token,
        tool.Params(item_id=child["id"], clear_parent=True, parent_id=container["id"], location_id=first["id"]),
    )
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
    if homebox_version != "0.27.0":
        pytest.skip("Explicit location overrides require Homebox 0.27.0")

    token = homebox_auth.token
    first = await homebox_client.create_location(token, "Override location A")
    second = await homebox_client.create_location(token, "Override location B")
    cleanup_locations.extend((first["id"], second["id"]))
    container = await _create_item(homebox_client, homebox_auth, cleanup_items, "Override container", first["id"])
    child = await _create_item(homebox_client, homebox_auth, cleanup_items, "Override child", container["id"])

    await homebox_client.update_item(
        token,
        child["id"],
        {"name": child["name"], "quantity": 1, "parentId": container["id"], "locationId": second["id"]},
    )
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

    await tool.execute(homebox_client, token, tool.Params(item_id=child["id"], location_id=first["id"]))
    moved = await _fresh_item(homebox_test_account, homebox_auth, child["id"])
    assert moved["parent"]["id"] == first["id"]
    assert moved.get("locationId") is None
    assert moved["location"]["id"] == first["id"]
