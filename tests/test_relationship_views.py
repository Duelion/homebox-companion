"""LLM-facing item views distinguish containment from physical location."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homebox_companion.core.exceptions import HomeboxTimeoutError
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

# GET /v1/entities summaries (0.26.2 and 0.27.0) load the parent without its
# entity type and carry no resolved location.
LOCATIONS = [{"id": "workshop", "name": "Workshop"}, {"id": "garage", "name": "Garage"}]
DIRECT_SUMMARY = {"id": "saw", "name": "Saw", "parent": {"id": "workshop", "name": "Workshop", "tags": []}}
NESTED_SUMMARY = {"id": "drill", "name": "Drill", "parent": {"id": "toolchest", "name": "Toolchest", "tags": []}}


def _summary_client(*items: dict) -> MagicMock:
    client = MagicMock()
    client.list_items = AsyncMock(return_value={"items": list(items), "total": len(items)})
    client.list_locations = AsyncMock(return_value=LOCATIONS)
    client.get_item = AsyncMock()
    return client


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


def test_omitted_location_with_item_parent_has_no_location() -> None:
    """0.27 omits ``location`` when no location ancestor exists."""
    result = ItemView.from_dict(
        {"id": "drill", "parent": {"id": "toolchest", "name": "Toolchest", "entityType": {"isLocation": False}}}
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


def test_untyped_detail_parent_is_reported_as_item() -> None:
    """Detail queries load the parent's type, so an untyped parent has none; Homebox treats it as an item."""
    result = ItemView.from_dict(
        {"id": "drill", "parent": {"id": "crate", "name": "Crate"}, "location": {"id": "garage", "name": "Garage"}},
        untyped_parent_is_item=True,
    )

    assert result.parent is not None and result.parent.name == "Crate"
    assert result.location is not None and result.location.name == "Garage"


@pytest.mark.parametrize("view_type", [CompactItemView, ItemView])
def test_untyped_summary_parent_is_classified_by_known_locations(
    view_type: type[CompactItemView] | type[ItemView],
) -> None:
    location_ids = {loc["id"] for loc in LOCATIONS}

    direct = view_type.from_dict(DIRECT_SUMMARY, location_ids=location_ids)
    nested = view_type.from_dict(NESTED_SUMMARY, location_ids=location_ids)

    assert direct.location is not None and direct.location.name == "Workshop"
    assert direct.parent is None
    assert nested.location is None
    assert nested.parent is not None and nested.parent.name == "Toolchest"


def test_entity_type_metadata_wins_over_known_locations() -> None:
    result = ItemView.from_dict(
        {"id": "x", "parent": {"id": "workshop", "name": "Workshop", "entityType": {"isLocation": False}}},
        location_ids={"workshop"},
    )

    assert result.location is None
    assert result.parent is not None


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
async def test_get_item_returns_both_relationships() -> None:
    client = MagicMock()
    client.get_item = AsyncMock(return_value=NESTED_ITEM)
    tool = GetItemTool()

    result = await tool.execute(client, "token", tool.Params(item_id="drill"))

    assert result.data["parent"]["name"] == "Toolchest"
    assert result.data["location"]["name"] == "Workshop"


@pytest.mark.asyncio
async def test_asset_lookup_reads_details_because_asset_summaries_are_untyped() -> None:
    client = MagicMock()
    # GET /v1/assets/{id} returns summaries: untyped parent, no resolved location.
    client.get_item_by_asset_id = AsyncMock(return_value=NESTED_SUMMARY)
    client.get_item = AsyncMock(return_value=NESTED_ITEM)
    tool = GetItemByAssetIdTool()

    result = await tool.execute(client, "token", tool.Params(asset_id="000-001"))

    client.get_item.assert_awaited_once_with("token", "drill")
    assert result.data["parent"]["name"] == "Toolchest"
    assert result.data["location"]["name"] == "Workshop"


@pytest.mark.asyncio
@pytest.mark.parametrize("compact", [True, False])
@pytest.mark.parametrize(
    "tool_type,params",
    [
        (ListItemsTool, {}),
        (SearchItemsTool, {"query": "tool"}),
    ],
)
async def test_summary_tools_classify_real_summaries_without_fetching_details(
    tool_type: type, params: dict[str, str], compact: bool
) -> None:
    client = _summary_client(NESTED_SUMMARY, DIRECT_SUMMARY)
    tool = tool_type()

    result = await tool.execute(client, "token", tool.Params(**params, compact=compact))

    by_id = {item["id"]: item for item in result.data["items"]}
    assert by_id["saw"]["location"]["name"] == "Workshop"
    assert by_id["saw"]["parent"] is None
    assert by_id["drill"]["parent"]["name"] == "Toolchest"
    assert by_id["drill"]["location"] is None
    client.list_locations.assert_awaited_once_with("token", include_archived=True)
    client.get_item.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"location_id": "garage"}, {"location_name": "garage"}])
async def test_location_filtered_list_reports_filtered_location_for_nested_items(params: dict[str, str]) -> None:
    """A nested result of a 0.27 location filter is an override match, so it lives there."""
    client = _summary_client(NESTED_SUMMARY)
    tool = ListItemsTool()

    result = await tool.execute(client, "token", tool.Params(**params))

    summary = result.data["items"][0]
    assert summary["parent"]["name"] == "Toolchest"
    assert summary["location"]["id"] == "garage"
    assert summary["location"]["name"] == "Garage"
    # One location fetch serves both name resolution and classification.
    client.list_locations.assert_awaited_once_with("token", include_archived=True)


@pytest.mark.asyncio
async def test_location_name_prefers_active_but_reaches_archived_locations() -> None:
    client = _summary_client()
    client.list_locations = AsyncMock(
        return_value=[
            {"id": "old-garage", "name": "Garage", "archived": True},
            {"id": "garage", "name": "Garage", "archived": False},
            {"id": "attic", "name": "Attic", "archived": True},
        ]
    )
    tool = ListItemsTool()

    await tool.execute(client, "token", tool.Params(location_name="garage"))
    assert client.list_items.await_args.kwargs["location_id"] == "garage"
    await tool.execute(client, "token", tool.Params(location_name="attic"))
    assert client.list_items.await_args.kwargs["location_id"] == "attic"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_type,params", [(ListItemsTool, {}), (SearchItemsTool, {"query": "saw"})])
async def test_failed_location_fetch_leaves_parents_unclassified(tool_type: type, params: dict[str, str]) -> None:
    client = _summary_client(DIRECT_SUMMARY)
    client.list_locations = AsyncMock(side_effect=HomeboxTimeoutError("slow"))
    tool = tool_type()

    result = await tool.execute(client, "token", tool.Params(**params))

    assert result.success is True
    assert result.data["items"][0]["location"] is None
    assert result.data["items"][0]["parent"] is None


@pytest.mark.asyncio
async def test_archived_location_parent_is_classified_as_location() -> None:
    client = _summary_client({"id": "old", "name": "Old", "parent": {"id": "attic", "name": "Attic"}})
    # Homebox omits archived locations unless includeArchived is requested.
    client.list_locations = AsyncMock(
        side_effect=lambda token, include_archived=False: (
            [*LOCATIONS, {"id": "attic", "name": "Attic", "archived": True}] if include_archived else LOCATIONS
        )
    )
    tool = SearchItemsTool()

    result = await tool.execute(client, "token", tool.Params(query="old"))

    summary = result.data["items"][0]
    assert summary["location"]["name"] == "Attic"
    assert summary["parent"] is None


@pytest.mark.asyncio
async def test_summaries_sort_by_location_then_container_then_name() -> None:
    items = [
        {"id": "b", "name": "B", "parent": {"id": "workshop", "name": "Workshop"}},
        {"id": "c", "name": "C", "parent": {"id": "toolchest", "name": "Toolchest"}},
        {"id": "a", "name": "A", "parent": {"id": "garage", "name": "Garage"}},
        {"id": "d", "name": "D", "parent": {"id": "bin", "name": "Bin"}},
    ]
    client = _summary_client(*items)
    tool = SearchItemsTool()

    result = await tool.execute(client, "token", tool.Params(query="x"))

    # Unknown locations sort first, grouped by container; then by location name.
    assert [item["id"] for item in result.data["items"]] == ["d", "c", "a", "b"]


@pytest.mark.asyncio
async def test_delete_confirmation_uses_physical_location_not_container() -> None:
    client = MagicMock()
    client.get_item = AsyncMock(return_value=NESTED_ITEM)

    info = await ToolExecutor(client).get_display_info("delete_item", {"item_id": "drill"}, "token")

    assert info.location == "Workshop"


@pytest.mark.asyncio
async def test_delete_confirmation_does_not_label_container_as_location() -> None:
    """0.26 nested details, and 0.27 ones without a location ancestor, have a typed parent and no location."""
    client = MagicMock()
    client.get_item = AsyncMock(
        return_value={
            "id": "drill",
            "name": "Drill",
            "parent": {"id": "toolchest", "name": "Toolchest", "entityType": {"isLocation": False}},
        }
    )

    info = await ToolExecutor(client).get_display_info("delete_item", {"item_id": "drill"}, "token")

    assert info.location is None


@pytest.mark.asyncio
async def test_delete_confirmation_uses_location_parent_on_026() -> None:
    client = MagicMock()
    client.get_item = AsyncMock(
        return_value={
            "id": "saw",
            "name": "Saw",
            "parent": {"id": "workshop", "name": "Workshop", "entityType": {"isLocation": True}},
        }
    )

    info = await ToolExecutor(client).get_display_info("delete_item", {"item_id": "saw"}, "token")

    assert info.location == "Workshop"


CUSTOM_FIELDS = [
    {"name": "QA Material 材料", "type": "text", "textValue": "木材"},
    {"name": "Duplicate", "type": "text", "textValue": ""},
    {"name": "Duplicate", "type": "number", "numberValue": 0},
    {"name": "Fraction", "type": "number", "numberValue": 1.25},
    {"name": "Enabled", "type": "boolean", "booleanValue": False},
]


def test_detailed_custom_fields_preserve_types_and_bound_metadata() -> None:
    upstream = [{**field, "id": "upstream-id", "secretMetadata": "excluded"} for field in CUSTOM_FIELDS]
    result = ItemView.from_dict({**NESTED_ITEM, "fields": upstream}).model_dump(by_alias=True)
    assert [
        {key: field[key] for key in original} for field, original in zip(result["fields"], CUSTOM_FIELDS, strict=True)
    ] == CUSTOM_FIELDS
    assert all(set(field) == {"name", "type", "textValue", "numberValue", "booleanValue"} for field in result["fields"])
    assert type(result["fields"][2]["numberValue"]) is int
    assert result["fields"][4]["booleanValue"] is False
    assert result["parent"]["url"].endswith("/item/toolchest")
    assert result["location"]["url"].endswith("/location/workshop")
    assert upstream[0]["secretMetadata"] == "excluded"
    assert "fields" not in CompactItemView.from_dict({**NESTED_ITEM, "fields": upstream}).model_dump()


@pytest.mark.parametrize("data", [{"id": "item"}, {"id": "item", "fields": None}])
def test_missing_custom_fields_are_empty(data: dict) -> None:
    assert ItemView.from_dict(data).model_dump()["fields"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_type,params", [(GetItemTool, {"item_id": "drill"}), (GetItemByAssetIdTool, {"asset_id": "000-001"})]
)
async def test_detail_tools_expose_custom_values(tool_type: type, params: dict) -> None:
    client = MagicMock()
    client.get_item = AsyncMock(return_value={**NESTED_ITEM, "fields": CUSTOM_FIELDS})
    client.get_item_by_asset_id = AsyncMock(return_value=NESTED_SUMMARY)
    tool = tool_type()
    result = await tool.execute(client, "token", tool.Params(**params))
    assert [
        {key: field[key] for key in original}
        for field, original in zip(result.data["fields"], CUSTOM_FIELDS, strict=True)
    ] == CUSTOM_FIELDS


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_type,params", [(ListItemsTool, {}), (SearchItemsTool, {"query": "drill"})])
@pytest.mark.parametrize("compact", [True, False])
async def test_summary_custom_field_projection(tool_type: type, params: dict, compact: bool) -> None:
    client = _summary_client({**NESTED_SUMMARY, "fields": CUSTOM_FIELDS})
    tool = tool_type()
    result = await tool.execute(client, "token", tool.Params(**params, compact=compact))
    [item] = result.data["items"]
    if compact:
        assert "fields" not in item
    else:
        assert item["fields"][0]["textValue"] == "木材"
    assert "fetch get_item" in tool.Params.model_fields["compact"].description
