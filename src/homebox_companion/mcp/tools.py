"""MCP tool definitions for Homebox operations.

This module defines the tools that the MCP server exposes to LLM assistants.
Each tool is a frozen dataclass with a nested Pydantic Params model for
automatic JSON schema generation and parameter validation.

Tool Classification:
- READ: Auto-execute, no approval needed
- WRITE: Requires explicit user approval
- DESTRUCTIVE: Requires approval + additional confirmation
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import Field

from ..homebox.views import CompactItemView, ItemView, LocationView, add_tree_urls
from .types import Tool, ToolParams, ToolPermission, ToolResult

if TYPE_CHECKING:
    from ..homebox.client import HomeboxClient


def handle_tool_errors(
    func: Callable[..., Coroutine[Any, Any, ToolResult]],
) -> Callable[..., Coroutine[Any, Any, ToolResult]]:
    """Decorator to standardize error handling for tool execute methods.

    Catches exceptions, logs them, and returns a standardized ToolResult.
    """

    @wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> ToolResult:
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"{self.name} failed: {e}")
            return ToolResult(success=False, error=str(e))

    return wrapper


# =============================================================================
# READ-ONLY TOOLS
# =============================================================================


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

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        locations = await client.list_locations(
            token,
            filter_children=params.filter_children if params.filter_children else None,
        )
        # Convert to LocationView for URL generation
        locations = [LocationView.from_dict(loc).model_dump(by_alias=True) for loc in locations]
        logger.debug(f"list_locations returned {len(locations)} locations")
        return ToolResult(success=True, data=locations)


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

    @handle_tool_errors
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


@dataclass(frozen=True)
class ListLabelsTool:
    """List all labels available for categorizing items."""

    name: str = "list_labels"
    description: str = "List all labels available for categorizing items"
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        pass  # No parameters needed

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        labels = await client.list_labels(token)
        logger.debug(f"list_labels returned {len(labels)} labels")
        return ToolResult(success=True, data=labels)


@dataclass(frozen=True)
class ListItemsTool:
    """List items in the inventory with optional filtering and pagination."""

    name: str = "list_items"
    description: str = (
        "List items in the inventory with optional filtering and pagination. "
        "You can filter by location_name (preferred) or location_id. "
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
        label_ids: list[str] | None = Field(
            default=None,
            description="Optional list of label IDs to filter items by",
        )
        page: int | None = Field(
            default=None,
            description="Optional page number (1-indexed) for pagination",
        )
        page_size: int = Field(
            default=50,
            description="Number of items per page (default 50, max recommended 100)",
        )
        compact: bool = Field(
            default=True,
            description=(
                "If true, return only essential fields (id, name, location, quantity) "
                "to reduce payload size. Set to false for full item details."
            ),
        )

    @handle_tool_errors
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
            for loc in locations:
                if loc.get("name", "").lower() == params.location_name.lower():
                    resolved_location_id = loc.get("id")
                    logger.debug(
                        f"list_items: resolved location_name '{params.location_name}' "
                        f"to id '{resolved_location_id}'"
                    )
                    break
            else:
                # Location not found
                return ToolResult(
                    success=False,
                    error=f"Location '{params.location_name}' not found",
                )

        items = await client.list_items(
            token,
            location_id=resolved_location_id,
            label_ids=params.label_ids,
            page=params.page,
            page_size=params.page_size,
        )

        if params.compact:
            items = [CompactItemView.from_dict(item).model_dump(by_alias=True) for item in items]
            logger.debug(f"list_items returned {len(items)} items (compact mode)")
        else:
            # Use ItemView for consistent URL generation
            items = [ItemView.from_dict(item).model_dump(by_alias=True) for item in items]
            logger.debug(f"list_items returned {len(items)} items")

        return ToolResult(success=True, data=items)


@dataclass(frozen=True)
class SearchItemsTool:
    """Search items by text query."""

    name: str = "search_items"
    description: str = (
        "Search items by text query. Use this for semantic searches like 'find rope', "
        "'items for building X', or any text-based search. More efficient than listing all items."
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        query: str = Field(
            description="Search query string (searches name, description, etc.)"
        )
        limit: int = Field(
            default=50,
            description="Maximum number of results to return (default 50)",
        )
        compact: bool = Field(
            default=True,
            description=(
                "If true, return only essential fields (id, name, location, quantity). "
                "Set to false for full item details."
            ),
        )

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        items = await client.search_items(token, query=params.query, limit=params.limit)

        if params.compact:
            items = [CompactItemView.from_dict(item).model_dump(by_alias=True) for item in items]
            logger.debug(
                f"search_items('{params.query}') returned {len(items)} items (compact)"
            )
        else:
            # Use ItemView for consistent URL generation
            items = [ItemView.from_dict(item).model_dump(by_alias=True) for item in items]
            logger.debug(f"search_items('{params.query}') returned {len(items)} items")

        return ToolResult(success=True, data=items)


@dataclass(frozen=True)
class GetItemTool:
    """Get full item details by ID."""

    name: str = "get_item"
    description: str = "Get full item details by ID"
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to fetch")

    @handle_tool_errors
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

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        stats = await client.get_statistics(token)
        logger.debug(f"get_statistics returned: {stats.get('totalItems', 0)} items")
        return ToolResult(success=True, data=stats)


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

    @handle_tool_errors
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

    @handle_tool_errors
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


@dataclass(frozen=True)
class GetStatisticsByLocationTool:
    """Get item counts grouped by location."""

    name: str = "get_statistics_by_location"
    description: str = (
        "Get item counts grouped by location. Useful for analytics queries "
        "like 'which location has the most items?'"
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        pass  # No parameters needed

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        stats = await client.get_statistics_by_location(token)
        logger.debug(f"get_statistics_by_location returned {len(stats)} locations")
        return ToolResult(success=True, data=stats)


@dataclass(frozen=True)
class GetStatisticsByLabelTool:
    """Get item counts grouped by label."""

    name: str = "get_statistics_by_label"
    description: str = (
        "Get item counts grouped by label. Useful for analytics queries "
        "like 'how many items are tagged Electronics?'"
    )
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        pass  # No parameters needed

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        stats = await client.get_statistics_by_label(token)
        logger.debug(f"get_statistics_by_label returned {len(stats)} labels")
        return ToolResult(success=True, data=stats)


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

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        path = await client.get_item_path(token, params.item_id)
        logger.debug(f"get_item_path for {params.item_id} returned {len(path)} path elements")
        return ToolResult(success=True, data=path)


@dataclass(frozen=True)
class GetAttachmentTool:
    """Get an attachment's content by ID."""

    name: str = "get_attachment"
    description: str = "Get an attachment's content by ID (returns base64 encoded content)"
    permission: ToolPermission = ToolPermission.READ

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item the attachment belongs to")
        attachment_id: str = Field(description="ID of the attachment to fetch")

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        try:
            content_bytes, content_type = await client.get_attachment(
                token, params.item_id, params.attachment_id
            )
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


@dataclass(frozen=True)
class CreateItemTool:
    """Create a new item in Homebox."""

    name: str = "create_item"
    description: str = "Create a new item in Homebox"
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        name: str = Field(description="Name of the item")
        location_id: str = Field(description="ID of the location to place the item")
        description: str = Field(default="", description="Optional description")
        quantity: int = Field(default=1, ge=1, description="Quantity of the item (default: 1)")
        label_ids: list[str] | None = Field(
            default=None,
            description="Optional list of label IDs to apply",
        )

    @handle_tool_errors
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
            label_ids=params.label_ids or [],
        )
        result = await client.create_item(token, item_data)
        logger.info(f"create_item created item: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@dataclass(frozen=True)
class UpdateItemTool:
    """Update an existing item."""

    name: str = "update_item"
    description: str = "Update an existing item's name, description, location, or quantity"
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to update")
        name: str | None = Field(default=None, description="Optional new name")
        description: str | None = Field(default=None, description="Optional new description")
        location_id: str | None = Field(default=None, description="Optional new location ID")
        quantity: int | None = Field(default=None, ge=1, description="Optional new quantity")

    @handle_tool_errors
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
            "description": (
                params.description
                if params.description is not None
                else current.get("description", "")
            ),
            "quantity": params.quantity if params.quantity is not None else current.get("quantity", 1),
            "insured": current.get("insured", False),
            "archived": current.get("archived", False),
            "assetId": current.get("assetId", ""),
            "notes": current.get("notes", ""),
        }

        # Handle location - use new location_id if provided, else preserve current
        if params.location_id is not None:
            update_data["locationId"] = params.location_id
        elif current.get("location"):
            update_data["locationId"] = current["location"].get("id")

        # Preserve labels if present
        if current.get("labels"):
            update_data["labels"] = [
                {"id": label.get("id")} for label in current["labels"] if label.get("id")
            ]

        result = await client.update_item(token, params.item_id, update_data)
        logger.info(f"update_item updated item: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


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

    @handle_tool_errors
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

    @handle_tool_errors
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
            description=(
                params.description
                if params.description is not None
                else current.get("description", "")
            ),
            parent_id=resolved_parent_id,
        )
        logger.info(f"update_location updated location: {result.get('name', 'unknown')}")
        return ToolResult(success=True, data=result)


@dataclass(frozen=True)
class UploadAttachmentTool:
    """Upload an attachment to an item."""

    name: str = "upload_attachment"
    description: str = "Upload an attachment to an item"
    permission: ToolPermission = ToolPermission.WRITE

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to attach to")
        file_base64: str = Field(description="File content as base64 encoded string")
        filename: str = Field(description="Name for the uploaded file")
        mime_type: str = Field(
            default="image/jpeg",
            description="MIME type of the file (default: image/jpeg)",
        )
        attachment_type: str = Field(
            default="photo",
            description="Type of attachment: 'photo', 'manual', 'warranty', etc.",
        )

    @handle_tool_errors
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

    @handle_tool_errors
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


@dataclass(frozen=True)
class DeleteItemTool:
    """Delete an item from Homebox."""

    name: str = "delete_item"
    description: str = "Delete an item from Homebox. This action cannot be undone."
    permission: ToolPermission = ToolPermission.DESTRUCTIVE

    class Params(ToolParams):
        item_id: str = Field(description="ID of the item to delete")

    @handle_tool_errors
    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: Params,
    ) -> ToolResult:
        await client.delete_item(token, params.item_id)
        logger.info(f"delete_item deleted item: {params.item_id}")
        return ToolResult(success=True, data={"deleted_id": params.item_id})


# =============================================================================
# TOOL DISCOVERY
# =============================================================================


def get_tools() -> list[Tool]:
    """Discover and instantiate all Tool classes in this module.

    Uses Protocol-based type checking to find tools rather than fragile
    string matching or attribute inspection.

    Returns:
        List of tool instances, each satisfying the Tool protocol.
    """
    import inspect

    from pydantic import BaseModel

    tools: list[Tool] = []
    for _name, cls in globals().items():
        # Skip non-classes and abstract/protocol types
        if not inspect.isclass(cls):
            continue
        if cls is Tool:
            continue

        # Skip Pydantic models (views imported for tool responses)
        if issubclass(cls, BaseModel):
            continue

        # Try to instantiate and check if it satisfies the Tool protocol
        try:
            instance = cls()
            if isinstance(instance, Tool):
                tools.append(instance)
        except TypeError:
            # Class requires arguments or can't be instantiated
            continue

    return tools
