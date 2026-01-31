"""MCP tool definitions for Homebox operations.

This module defines the tools that the MCP server exposes to LLM assistants.
Each tool is a frozen dataclass with a nested Pydantic Params model for
automatic JSON schema generation and parameter validation.

Tool Classification:
- READ: Auto-execute, no approval needed
- WRITE: Requires explicit user approval
- DESTRUCTIVE: Requires approval + additional confirmation

Tools are registered using the @register_tool decorator for explicit discovery.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import Field

from ..homebox.views import CompactItemView, ItemView, LocationView, add_tree_urls
from .types import Tool, ToolParams, ToolPermission, ToolResult

if TYPE_CHECKING:
    from ..homebox.client import HomeboxClient


# =============================================================================
# TOOL REGISTRY
# =============================================================================

_TOOL_REGISTRY: list[type[Tool]] = []


def register_tool[T: type[Tool]](cls: T) -> T:
    """Decorator to register a tool class for discovery.

    This provides explicit tool registration rather than fragile
    introspection-based discovery.

    Example:
        >>> @register_tool
        ... @dataclass(frozen=True)
        ... class MyTool:
        ...     name: str = "my_tool"
        ...     ...
    """
    _TOOL_REGISTRY.append(cls)
    return cls


def get_tools() -> list[Tool]:
    """Get all registered tool instances.

    Returns:
        List of tool instances, each satisfying the Tool protocol.
    """
    return [cls() for cls in _TOOL_REGISTRY]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _sort_items_by_location_and_name(items: list[dict]) -> list[dict]:
    """Sort items by location name, then by item name.

    This helps the AI parse results more efficiently by grouping items
    by location and maintaining alphabetical order within each location.

    Args:
        items: List of item dicts with 'name' and 'location' fields.

    Returns:
        Sorted list of items.
    """
    return sorted(
        items,
        key=lambda item: (
            (item.get("location", {}) or {}).get("name", "").lower(),
            item.get("name", "").lower(),
        ),
    )


# =============================================================================
# READ-ONLY TOOLS
# =============================================================================


@register_tool
@dataclass(frozen=True)
class ListLocationsTool:
    """List all locations in Homebox inventory."""

    name: str = "list_locations"
    description: str = (
        "List all locations in Homebox inventory. Returns name, id, itemCount, and url "
        "for each location. Use this for listing/displaying locations - do NOT call "
        "get_location for each result."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        filter_children: bool = Field(
            default=False,
            description="If true, only return top-level locations",
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        locations = await client.list_locations(
            token,
            filter_children=params.filter_children or None,
        )
        # Convert to LocationView for URL generation
        locations = [LocationView.from_dict(loc).model_dump(by_alias=True) for loc in locations]
        logger.debug(f"list_locations returned {len(locations)} locations")
        return ToolResult(success=True, data=locations)


@register_tool
@dataclass(frozen=True)
class GetLocationTool:
    """Get a specific location with its child locations."""

    name: str = "get_location"
    description: str = (
        "Get a specific location's details including child locations. "
        "Only use this when user asks about a location's children or hierarchy - "
        "NOT needed for basic location listing."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        location_id: str = Field(description="The ID of the location to fetch")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        location = await client.get_location(token, params.location_id)
        # Convert to LocationView for URL generation
        location_view = LocationView.from_dict(location).model_dump(by_alias=True)
        logger.debug(f"get_location returned location: {location.get('name', 'unknown')}")
        return ToolResult(success=True, data=location_view)


@register_tool
@dataclass(frozen=True)
class ListTagsTool:
    """List all tags available for categorizing items."""

    name: str = "list_tags"
    description: str = "List all tags available for categorizing items"
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        pass  # No parameters needed

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        from ..core.config import settings

        tags = await client.list_tags(token)
        logger.debug(f"list_tags returned {len(tags)} tags")

        # Add URL to each tag for easy linking in chat
        base_url = settings.effective_link_base_url
        enriched_tags = [{**tag, "url": f"{base_url}/items?tags={tag.get('id', '')}"} for tag in tags]

        return ToolResult(success=True, data=enriched_tags)


@register_tool
@dataclass(frozen=True)
class ListItemsTool:
    """List items in the inventory with optional filtering and pagination."""

    name: str = "list_items"
    description: str = (
        "List items in the inventory with optional filtering. "
        "Set page_size to the user's requested count (e.g., 'list 100 items' -> page_size=100). "
        "For text-based searches, prefer using search_items instead."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        location_name: str | None = Field(
            default=None,
            description=(
                "Location name to filter items by (case-insensitive). "
                "Use this when the user specifies a location by name like 'Garage' or 'Kitchen'."
            ),
        )
        location_id: str | None = Field(
            default=None,
            description="Location UUID to filter items by. Use location_name instead when possible.",
        )
        tag_ids: list[str] | None = Field(
            default=None,
            description="Optional list of tag IDs to filter items by",
        )
        page: int | None = Field(
            default=None,
            description="Optional page number (1-indexed) for pagination",
        )
        page_size: int = Field(
            default=50,
            description="Number of items to return. Use the user's requested count if specified.",
        )
        compact: bool = Field(
            default=True,
            description=(
                "If true, return only essential fields (id, name, location, quantity, tags) "
                "to reduce payload size. Set to false for full item details."
            ),
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        # Resolve location_name to location_id if provided
        resolved_location_id = params.location_id
        if params.location_name and not params.location_id:
            locations = await client.list_locations(token)
            # Find ALL matching locations (case-insensitive)
            matches = [loc for loc in locations if loc.get("name", "").lower() == params.location_name.lower()]

            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Location '{params.location_name}' not found",
                )

            if len(matches) > 1:
                # Ambiguous: multiple locations with same name
                match_ids = [m.get("id", "unknown") for m in matches]
                logger.warning(
                    f"list_items: location_name '{params.location_name}' matched "
                    f"{len(matches)} locations: {match_ids}. Using first match."
                )
                return ToolResult(
                    success=False,
                    error=(
                        f"Ambiguous location name '{params.location_name}' matches "
                        f"{len(matches)} locations. Use location_id instead: {match_ids}"
                    ),
                )

            # Single match - use it
            resolved_location_id = matches[0].get("id")
            logger.debug(f"list_items: resolved location_name '{params.location_name}' to id '{resolved_location_id}'")

        response = await client.list_items(
            token,
            location_id=resolved_location_id,
            tag_ids=params.tag_ids,
            page=params.page,
            page_size=params.page_size,
        )

        # Extract items from pagination response
        items = response.get("items", [])

        if params.compact:
            items = [CompactItemView.from_dict(item).model_dump(by_alias=True) for item in items]
        else:
            # Use ItemView for consistent URL generation
            items = [ItemView.from_dict(item).model_dump(by_alias=True) for item in items]

        # Sort by location name, then item name for easier AI parsing
        items = _sort_items_by_location_and_name(items)
        logger.debug(f"list_items returned {len(items)} items (sorted by location/name)")

        # Include pagination metadata so LLM knows if there are more items
        return ToolResult(
            success=True,
            data={
                "items": items,
                "pagination": {
                    "page": response.get("page", 1),
                    "page_size": response.get("pageSize", params.page_size),
                    "total": response.get("total", len(items)),
                    "items_returned": len(items),
                },
            },
        )


@register_tool
@dataclass(frozen=True)
class SearchItemsTool:
    """Search items by text query."""

    name: str = "search_items"
    description: str = (
        "Search items by text query. Use for semantic searches like 'find rope'. "
        "Set page_size to the user's requested count if specified."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        query: str = Field(description="Search query string (searches name, description, etc.)")
        page: int | None = Field(
            default=None,
            description="Optional page number (1-indexed) for pagination",
        )
        page_size: int = Field(
            default=50,
            description="Number of items to return. Use the user's requested count if specified.",
        )
        compact: bool = Field(
            default=True,
            description=(
                "If true, return only essential fields (id, name, location, quantity, tags). "
                "Set to false for full item details."
            ),
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        response = await client.list_items(
            token,
            query=params.query,
            page=params.page,
            page_size=params.page_size,
        )

        # Extract items from pagination response
        items = response.get("items", [])

        if params.compact:
            items = [CompactItemView.from_dict(item).model_dump(by_alias=True) for item in items]
        else:
            # Use ItemView for consistent URL generation
            items = [ItemView.from_dict(item).model_dump(by_alias=True) for item in items]

        # Sort by location name, then item name for easier AI parsing
        items = _sort_items_by_location_and_name(items)
        logger.debug(f"search_items('{params.query}') returned {len(items)} items (sorted by location/name)")

        # Include pagination metadata so LLM knows if there are more items
        return ToolResult(
            success=True,
            data={
                "items": items,
                "pagination": {
                    "page": response.get("page", 1),
                    "page_size": response.get("pageSize", params.page_size),
                    "total": response.get("total", len(items)),
                    "items_returned": len(items),
                },
            },
        )


@register_tool
@dataclass(frozen=True)
class GetItemTool:
    """Get full item details by ID."""

    name: str = "get_item"
    description: str = "Get full item details by ID"
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to fetch")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        item = await client.get_item(token, params.item_id)
        # Use ItemView for consistent URL generation
        item_view = ItemView.from_dict(item).model_dump(by_alias=True)
        logger.debug(f"get_item returned item: {item.get('name', 'unknown')}")
        return ToolResult(success=True, data=item_view)


@register_tool
@dataclass(frozen=True)
class GetStatisticsTool:
    """Get inventory statistics overview."""

    name: str = "get_statistics"
    description: str = (
        "Get inventory statistics overview. Returns counts and totals without loading "
        "full item data. Use for questions like 'how many items' or 'total inventory value'."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        pass  # No parameters needed

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        stats = await client.get_statistics(token)
        logger.debug(f"get_statistics returned: {stats.get('totalItems', 0)} items")
        return ToolResult(success=True, data=stats)


@register_tool
@dataclass(frozen=True)
class GetItemByAssetIdTool:
    """Get item by its asset ID."""

    name: str = "get_item_by_asset_id"
    description: str = (
        "Get item by its asset ID. Look up an item using its printed asset ID "
        "(e.g., '000-085'). Useful for barcode scanning or when user provides an asset ID."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        asset_id: str = Field(description="The asset ID to look up (e.g., '000-085')")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        item = await client.get_item_by_asset_id(token, params.asset_id)
        # Use ItemView for consistent URL generation
        item_view = ItemView.from_dict(item).model_dump(by_alias=True)
        logger.debug(f"get_item_by_asset_id({params.asset_id}) returned: {item.get('name', 'unknown')}")
        return ToolResult(success=True, data=item_view)


@register_tool
@dataclass(frozen=True)
class GetLocationTreeTool:
    """Get hierarchical location tree."""

    name: str = "get_location_tree"
    description: str = (
        "Get hierarchical location tree. Returns locations in a tree structure "
        "showing parent-child relationships. More efficient than multiple get_location calls."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        with_items: bool = Field(
            default=False,
            description="If true, include items in the tree structure",
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        tree = await client.get_location_tree(token, with_items=params.with_items)
        # Add URLs recursively to all nodes (locations and items)
        for node in tree:
            add_tree_urls(node)
        logger.debug(f"get_location_tree returned {len(tree)} top-level nodes")
        return ToolResult(success=True, data=tree)


@register_tool
@dataclass(frozen=True)
class GetStatisticsByLocationTool:
    """Get item counts grouped by location."""

    name: str = "get_statistics_by_location"
    description: str = (
        "Get item counts grouped by location. Useful for analytics queries like 'which location has the most items?'"
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        pass  # No parameters needed

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        stats = await client.get_statistics_by_location(token)
        logger.debug(f"get_statistics_by_location returned {len(stats)} locations")
        return ToolResult(success=True, data=stats)


@register_tool
@dataclass(frozen=True)
class GetStatisticsByLabelTool:
    """Get item counts grouped by label."""

    name: str = "get_statistics_by_label"
    description: str = (
        "Get item counts grouped by label. Useful for analytics queries like 'how many items are tagged Electronics?'"
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        pass  # No parameters needed

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        stats = await client.get_statistics_by_label(token)
        logger.debug(f"get_statistics_by_label returned {len(stats)} labels")
        return ToolResult(success=True, data=stats)


@register_tool
@dataclass(frozen=True)
class GetItemPathTool:
    """Get the full hierarchical path of an item."""

    name: str = "get_item_path"
    description: str = (
        "Get the full hierarchical path of an item. Returns the location chain "
        "from root to the item's location. Useful for telling users exactly where to find an item."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        path = await client.get_item_path(token, params.item_id)
        logger.debug(f"get_item_path for {params.item_id} returned {len(path)} path elements")
        return ToolResult(success=True, data=path)


@register_tool
@dataclass(frozen=True)
class GetAttachmentTool:
    """Get an attachment's content by ID."""

    name: str = "get_attachment"
    description: str = "Get an attachment's content by ID (returns base64 encoded content)"
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item the attachment belongs to")
        attachment_id: str = Field(description="ID of the attachment to fetch")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        try:
            content_bytes, content_type = await client.get_attachment(token, params.item_id, params.attachment_id)
            # Encode bytes as base64 for JSON transport
            encoded = base64.b64encode(content_bytes).decode("utf-8")
            logger.debug(f"get_attachment fetched {len(content_bytes)} bytes")
            return ToolResult(
                success=True,
                data={
                    "content_base64": encoded,
                    "content_type": content_type,
                    "size_bytes": len(content_bytes),
                },
            )
        except FileNotFoundError:
            return ToolResult(success=False, error="Attachment not found")


# =============================================================================
# WRITE TOOLS
# =============================================================================


@register_tool
@dataclass(frozen=True)
class CreateItemTool:
    """Create a new item in Homebox."""

    name: str = "create_item"
    description: str = (
        "Create a new item in Homebox with basic fields only (name, description, "
        "quantity, location, tags). Does NOT support: notes, purchase_price, "
        "manufacturer, model_number, or serial_number - inform the user if they "
        "request these, and offer to update the items afterward."
    )
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        name: str = Field(description="Name of the item")
        location_id: str = Field(description="ID of the location to place the item")
        description: str = Field(default="", description="Optional description")
        quantity: int = Field(default=1, ge=1, description="Quantity of the item (default: 1)")
        tag_ids: list[str] | None = Field(
            default=None,
            description="Optional list of tag IDs to apply",
        )
        parent_id: str | None = Field(
            default=None,
            description="Optional parent item ID to nest this item under",
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        from ..homebox.models import ItemCreate

        item_data = ItemCreate(
            name=params.name,
            location_id=params.location_id,
            description=params.description,
            quantity=params.quantity,
            tag_ids=params.tag_ids or [],
            parent_id=params.parent_id,
        )
        result = await client.create_item(token, item_data)
        logger.info(f"create_item created item: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@register_tool
@dataclass(frozen=True)
class UpdateItemTool:
    """Update an existing item."""

    name: str = "update_item"
    description: str = (
        "Update an existing item. Automatically fetches current values, so do NOT call "
        "get_item first. Only provide fields you want to change. For tag_ids, pass the "
        "complete list of tag IDs (existing + new) since it replaces all tags. "
        "IMPORTANT: You MUST explain the reason for this update in the message content "
        "BEFORE calling this tool."
    )
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to update")
        name: str | None = Field(default=None, description="Optional new name")
        description: str | None = Field(default=None, description="Optional new description")
        location_id: str | None = Field(default=None, description="Optional new location ID")
        quantity: int | None = Field(default=None, ge=1, description="Optional new quantity")
        purchase_price: float | None = Field(
            default=None, ge=0, alias="purchasePrice", description="Optional new purchase price"
        )
        tag_ids: list[str] | None = Field(
            default=None,
            description=(
                "Complete list of tag IDs for the item. To ADD a tag, include all "
                "existing tag IDs plus the new one. To REMOVE a tag, omit it from "
                "the list. Pass null/omit to keep tags unchanged."
            ),
        )
        notes: str | None = Field(default=None, description="Optional new notes text")
        insured: bool | None = Field(default=None, description="Optional insurance status")
        archived: bool | None = Field(default=None, description="Optional archive status")
        manufacturer: str | None = Field(default=None, description="Optional new manufacturer")
        model_number: str | None = Field(default=None, alias="modelNumber", description="Optional new model number")
        serial_number: str | None = Field(default=None, alias="serialNumber", description="Optional new serial number")
        purchase_from: str | None = Field(
            default=None, alias="purchaseFrom", description="Optional new purchase location"
        )
        parent_id: str | None = Field(
            default=None,
            description="New parent item ID to nest this item under (use with clear_parent=False)",
        )
        clear_parent: bool = Field(
            default=False,
            description="If true, remove parent to make this a top-level item",
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        # First get the current item to preserve unchanged fields
        current = await client.get_item(token, params.item_id)

        # Build update payload preserving unchanged fields from current item
        update_data = {
            "id": params.item_id,
            "name": params.name if params.name is not None else current.get("name"),
            "description": (params.description if params.description is not None else current.get("description", "")),
            "quantity": params.quantity if params.quantity is not None else current.get("quantity", 1),
            "insured": params.insured if params.insured is not None else current.get("insured", False),
            "archived": params.archived if params.archived is not None else current.get("archived", False),
            "assetId": current.get("assetId", ""),
            "notes": params.notes if params.notes is not None else current.get("notes", ""),
            "manufacturer": params.manufacturer if params.manufacturer is not None else current.get("manufacturer", ""),
            "modelNumber": params.model_number if params.model_number is not None else current.get("modelNumber", ""),
            "serialNumber": (
                params.serial_number if params.serial_number is not None else current.get("serialNumber", "")
            ),
            "purchaseFrom": (
                params.purchase_from if params.purchase_from is not None else current.get("purchaseFrom", "")
            ),
        }

        # Handle purchasePrice - use new value if provided, else preserve current
        if params.purchase_price is not None:
            update_data["purchasePrice"] = params.purchase_price
        elif current.get("purchasePrice") is not None:
            update_data["purchasePrice"] = current.get("purchasePrice")

        # Handle location - use new location_id if provided, else preserve current
        if params.location_id is not None:
            update_data["locationId"] = params.location_id
        elif current.get("location"):
            update_data["locationId"] = current["location"].get("id")

        # Handle tags - use correct API field name "tagIds" with flat string array
        if params.tag_ids is not None:
            update_data["tagIds"] = params.tag_ids
        elif current.get("tags"):
            # Preserve existing tags using correct format
            update_data["tagIds"] = [tag.get("id") for tag in current["tags"] if tag.get("id")]

        # Handle parent - determine parentId based on clear_parent flag
        if params.clear_parent:
            update_data["parentId"] = None
        elif params.parent_id is not None:
            update_data["parentId"] = params.parent_id
        else:
            update_data["parentId"] = current.get("parent", {}).get("id")

        result = await client.update_item(token, params.item_id, update_data)
        logger.info(f"update_item updated item: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@register_tool
@dataclass(frozen=True)
class CreateLocationTool:
    """Create a new location in Homebox."""

    name: str = "create_location"
    description: str = "Create a new location in Homebox"
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        name: str = Field(description="Name of the location")
        description: str = Field(default="", description="Optional description")
        parent_id: str | None = Field(
            default=None,
            description="Optional parent location ID for nesting",
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        result = await client.create_location(
            token,
            name=params.name,
            description=params.description,
            parent_id=params.parent_id,
        )
        logger.info(f"create_location created location: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@register_tool
@dataclass(frozen=True)
class CreateTagTool:
    """Create a new tag in Homebox."""

    name: str = "create_tag"
    description: str = "Create a new tag in Homebox"
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        name: str = Field(description="Name of the tag")
        description: str = Field(default="", description="Optional description")
        color: str = Field(default="", description="Optional color for the tag")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        result = await client.create_tag(
            token,
            name=params.name,
            description=params.description,
            color=params.color,
        )
        logger.info(f"create_tag created tag: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@register_tool
@dataclass(frozen=True)
class UpdateLocationTool:
    """Update an existing location."""

    name: str = "update_location"
    description: str = "Update an existing location's name, description, or parent"
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        location_id: str = Field(description="ID of the location to update")
        name: str | None = Field(default=None, description="Optional new name")
        description: str | None = Field(default=None, description="Optional new description")
        parent_id: str | None = Field(
            default=None,
            description="New parent location ID (use with clear_parent=False)",
        )
        clear_parent: bool = Field(
            default=False,
            description="If true, remove parent to make this a top-level location",
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        # First get the current location to preserve fields
        current = await client.get_location(token, params.location_id)

        # Determine parent_id based on clear_parent flag and provided value
        if params.clear_parent:
            resolved_parent_id = None
        elif params.parent_id is not None:
            resolved_parent_id = params.parent_id
        else:
            resolved_parent_id = current.get("parent", {}).get("id")

        result = await client.update_location(
            token,
            location_id=params.location_id,
            name=params.name if params.name is not None else current.get("name", ""),
            description=(params.description if params.description is not None else current.get("description", "")),
            parent_id=resolved_parent_id,
        )
        logger.info(f"update_location updated location: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@register_tool
@dataclass(frozen=True)
class UpdateTagTool:
    """Update an existing tag."""

    name: str = "update_tag"
    description: str = "Update an existing tag's name, description, or color"
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        tag_id: str = Field(description="ID of the tag to update")
        name: str | None = Field(default=None, description="Optional new name")
        description: str | None = Field(default=None, description="Optional new description")
        color: str | None = Field(default=None, description="Optional new color")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        # Get the current tag to preserve fields not being updated
        current = await client.get_tag(token, params.tag_id)

        result = await client.update_tag(
            token,
            tag_id=params.tag_id,
            name=params.name if params.name is not None else current.get("name", ""),
            description=(params.description if params.description is not None else current.get("description", "")),
            color=params.color if params.color is not None else current.get("color", ""),
        )
        logger.info(f"update_tag updated tag: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@register_tool
@dataclass(frozen=True)
class UploadAttachmentTool:
    """Upload an attachment to an item."""

    name: str = "upload_attachment"
    description: str = "Upload an attachment to an item"
    permission: ToolPermission = ToolPermission.WRITE

    # Maximum base64 payload size: 10MB encoded ≈ 7.5MB decoded file
    MAX_BASE64_SIZE = 10 * 1024 * 1024

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to attach to")
        file_base64: str = Field(
            max_length=10 * 1024 * 1024,  # 10MB base64 ≈ 7.5MB file
            description="File content as base64 encoded string (max 10MB)",
        )
        filename: str = Field(description="Name for the uploaded file")
        mime_type: str = Field(
            default="image/jpeg",
            description="MIME type of the file (default: image/jpeg)",
        )
        attachment_type: str = Field(
            default="photo",
            description="Type of attachment: 'photo', 'manual', 'warranty', etc.",
        )

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        try:
            file_bytes = base64.b64decode(params.file_base64)
        except binascii.Error as e:
            logger.error(f"upload_attachment invalid base64: {e}")
            return ToolResult(success=False, error=f"Invalid base64 encoding: {e}")

        result = await client.upload_attachment(
            token,
            item_id=params.item_id,
            file_bytes=file_bytes,
            filename=params.filename,
            mime_type=params.mime_type,
            attachment_type=params.attachment_type,
        )
        logger.info(f"upload_attachment uploaded {params.filename} to item {params.item_id}")
        return ToolResult(success=True, data=result)


@register_tool
@dataclass(frozen=True)
class EnsureAssetIdsTool:
    """Ensure all items have asset IDs assigned."""

    name: str = "ensure_asset_ids"
    description: str = (
        "Ensure all items have asset IDs assigned. Assigns sequential asset IDs "
        "to all items that don't currently have one. Idempotent - existing IDs are not affected."
    )
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        pass  # No parameters needed

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        count = await client.ensure_asset_ids(token)
        logger.info(f"ensure_asset_ids assigned IDs to {count} items")
        return ToolResult(success=True, data={"items_updated": count})


# =============================================================================
# DESTRUCTIVE TOOLS
# =============================================================================


@register_tool
@dataclass(frozen=True)
class DeleteItemTool:
    """Delete an item from Homebox."""

    name: str = "delete_item"
    description: str = "Delete an item from Homebox. This action cannot be undone."
    permission: ToolPermission = ToolPermission.DESTRUCTIVE

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to delete")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        await client.delete_item(token, params.item_id)
        logger.info(f"delete_item deleted item: {params.item_id}")
        return ToolResult(success=True, data={"deleted_id": params.item_id})


@register_tool
@dataclass(frozen=True)
class DeleteTagTool:
    """Delete a tag from Homebox."""

    name: str = "delete_tag"
    description: str = "Delete a tag from Homebox. This action cannot be undone."
    permission: ToolPermission = ToolPermission.DESTRUCTIVE

    class Params(ToolParams):
        tag_id: str = Field(description="ID of the tag to delete")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        await client.delete_tag(token, params.tag_id)
        logger.info(f"delete_tag deleted tag: {params.tag_id}")
        return ToolResult(success=True, data={"deleted_id": params.tag_id})


@register_tool
@dataclass(frozen=True)
class DeleteLocationTool:
    """Delete a location from Homebox."""

    name: str = "delete_location"
    description: str = "Delete a location from Homebox. This action cannot be undone."
    permission: ToolPermission = ToolPermission.DESTRUCTIVE

    class Params(ToolParams):
        location_id: str = Field(description="ID of the location to delete")

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        await client.delete_location(token, params.location_id)
        logger.info(f"delete_location deleted location: {params.location_id}")
        return ToolResult(success=True, data={"deleted_id": params.location_id})
