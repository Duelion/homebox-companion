"""LLM-facing item views distinguish containment from physical location."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homebox_companion.homebox.views import CompactItemView, ItemView
from homebox_companion.mcp.executor import ToolExecutor
from homebox_companion.mcp.tools import (
    GetItemByAssetIdTool,
    GetItemTool,
    ListItemsTool,
    SearchItemsTool,
)

NESTED_ITEM = {
    "id": "drill",
    "name": "Drill",
    "parent": {"id": "toolchest", "name": "Toolchest", "entityType": {"isLocation": False}},
    "location": {"id": "workshop", "name": "Workshop"},
}


def test_detailed_view_keeps_container_and_physical_location_separate() -> None:
    result = ItemView.from_dict(NESTED_ITEM).model_dump(by_alias=True)

    assert result["parent"] == {
        "id": "toolchest",
        "name": "Toolchest",
        "url": "http://localhost:7745/item/toolchest",
    }
    assert result["location"]["id"] == "workshop"
    assert result["location"]["name"] == "Workshop"


def test_direct_location_has_no_parent_item() -> None:
    result = ItemView.from_dict(
        {
            "id": "drill",
            "name": "Drill",
            "parent": {"id": "workshop", "name": "Workshop", "entityType": {"isLocation": True}},
            "location": {"id": "workshop", "name": "Workshop"},
        }
    )

    assert result.location is not None and result.location.name == "Workshop"
    assert result.parent is None


@pytest.mark.parametrize("location_value", [None, {}])
def test_explicit_location_value_is_authoritative(location_value: object) -> None:
    result = ItemView.from_dict(
        {
            "id": "drill",
            "parent": {"id": "toolchest", "name": "Toolchest", "entityType": {"isLocation": False}},
            "location": location_value,
        }
    )

    assert result.location is None
    assert result.parent is not None and result.parent.name == "Toolchest"


def test_known_location_metadata_retains_legacy_location_fallback() -> None:
    result = ItemView.from_dict(
        {
            "id": "legacy",
            "parent": {"id": "workshop", "name": "Workshop", "entityType": {"isLocation": True}},
        }
    )

    assert result.location is not None and result.location.name == "Workshop"
    assert result.parent is None


def test_missing_relationship_metadata_is_left_unknown() -> None:
    result = ItemView.from_dict({"id": "unknown", "parent": {"id": "untyped", "name": "Untyped parent"}})

    assert result.location is None
    assert result.parent is None


def test_compact_summary_exposes_parent_and_unknown_location() -> None:
    result = CompactItemView.from_dict(
        {
            "id": "drill",
            "name": "Drill",
            "parent": {"id": "toolchest", "name": "Toolchest", "entityType": {"isLocation": False}},
        }
    ).model_dump(by_alias=True)

    assert result["location"] is None
    assert result["parent"]["id"] == "toolchest"
    assert result["parent"]["url"].endswith("/item/toolchest")
    assert "physicalLocation" not in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_type,param_name,param_value,client_method",
    [
        (GetItemTool, "item_id", "drill", "get_item"),
        (GetItemByAssetIdTool, "asset_id", "000-001", "get_item_by_asset_id"),
    ],
)
async def test_detailed_read_tools_return_both_relationships(
    tool_type: type, param_name: str, param_value: str, client_method: str
) -> None:
    client = MagicMock()
    setattr(client, client_method, AsyncMock(return_value=NESTED_ITEM))
    tool = tool_type()

    result = await tool.execute(client, "token", tool.Params(**{param_name: param_value}))

    assert result.data["parent"]["name"] == "Toolchest"
    assert result.data["location"]["name"] == "Workshop"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_type,params",
    [
        (ListItemsTool, {}),
        (SearchItemsTool, {"query": "drill"}),
    ],
)
async def test_summary_tools_do_not_fetch_details(tool_type: type, params: dict[str, str]) -> None:
    client = MagicMock()
    client.list_items = AsyncMock(return_value={"items": [NESTED_ITEM], "total": 1})
    client.get_item = AsyncMock()
    tool = tool_type()

    result = await tool.execute(client, "token", tool.Params(**params))

    summary = result.data["items"][0]
    assert summary["parent"]["name"] == "Toolchest"
    assert summary["location"]["name"] == "Workshop"
    client.get_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_confirmation_uses_physical_location_not_container() -> None:
    client = MagicMock()
    client.get_item = AsyncMock(return_value=NESTED_ITEM)

    info = await ToolExecutor(client).get_display_info("delete_item", {"item_id": "drill"}, "token")

    assert info.location == "Workshop"


@pytest.mark.asyncio
async def test_delete_confirmation_does_not_label_container_as_location() -> None:
    client = MagicMock()
    client.get_item = AsyncMock(
        return_value={
            "id": "drill",
            "name": "Drill",
            "parent": {"id": "toolchest", "name": "Toolchest"},
            "location": None,
        }
    )

    info = await ToolExecutor(client).get_display_info("delete_item", {"item_id": "drill"}, "token")

    assert info.location is None
