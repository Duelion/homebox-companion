"""MCP tool definitions for Homebox operations.

This module defines the tools that the MCP server exposes to LLM assistants.
Each tool wraps a corresponding HomeboxClient method with proper input/output
schemas and error handling.

Tool Classification:
- READ: Auto-execute, no approval needed
- WRITE: Requires explicit user approval
- DESTRUCTIVE: Requires approval + additional confirmation
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any

from loguru import logger

from ..homebox.client import HomeboxClient

# Sentinel value to distinguish "not provided" from "explicitly None"
_UNSET: Any = object()

# Truncation limits for tool results (reduces context window usage)
MAX_RESULT_ITEMS = 10  # Maximum items in list results
MAX_RESULT_CHARS = 4000  # Maximum characters for string data


def _compact_item(item: dict[str, Any]) -> dict[str, Any]:
    """Extract minimal fields from an item for compact responses.

    This reduces payload size significantly when full details aren't needed.
    Includes a pre-computed URL field for markdown link generation.

    Args:
        item: Full item dictionary

    Returns:
        Compact item with only essential fields plus URL
    """
    from ..core.config import settings

    location = item.get("location", {})
    location_name = location.get("name") if location else None
    location_id = location.get("id") if location else None

    # Handle None or missing description safely
    description = item.get("description") or ""
    truncated_desc = description[:100] + ("..." if len(description) > 100 else "")

    item_id = item.get("id")
    base_url = settings.effective_link_base_url

    return {
        "id": item_id,
        "name": item.get("name"),
        "description": truncated_desc,
        "quantity": item.get("quantity"),
        "location": location_name,
        "location_id": location_id,
        "location_url": f"{base_url}/location/{location_id}" if location_id else None,
        "assetId": item.get("assetId"),
        "url": f"{base_url}/item/{item_id}" if item_id else None,
    }


class ToolPermission(str, Enum):
    """Permission level required to execute a tool.

    READ: Safe to auto-execute, no side effects
    WRITE: Modifies data, requires user approval
    DESTRUCTIVE: Deletes data, requires approval + confirmation
    """
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


@dataclass
class ToolResult:
    """Standard result wrapper for tool execution.

    Attributes:
        success: Whether the operation succeeded
        data: The result data (on success) or None
        error: Error message (on failure) or None
    """
    success: bool
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for MCP response with truncation."""
        if self.success:
            return {"success": True, "data": self._truncate_data(self.data)}
        return {"success": False, "error": self.error}

    def _truncate_data(self, data: Any) -> Any:
        """Truncate large data to reduce context window usage."""
        if isinstance(data, list) and len(data) > MAX_RESULT_ITEMS:
            return {
                "items": data[:MAX_RESULT_ITEMS],
                "_truncated": True,
                "_total": len(data),
                "_showing": MAX_RESULT_ITEMS,
            }
        return data


@dataclass
class ToolMetadata:
    """Metadata for a tool, attached by the @tool decorator.

    Attributes:
        description: Human-readable description of the tool
        permission: Permission level required (READ, WRITE, DESTRUCTIVE)
        parameters: JSON schema for the tool's parameters
    """
    description: str
    permission: ToolPermission
    parameters: dict[str, Any]


def tool(
    description: str,
    permission: ToolPermission,
    parameters: dict[str, Any] | None = None,
):
    """Decorator to register a method as an MCP tool with metadata.

    This decorator attaches metadata directly to the method, which is then
    collected by HomeboxMCPTools.get_tool_metadata(). This co-locates the
    tool definition with its implementation for better maintainability.

    Args:
        description: Human-readable description of what the tool does
        permission: Permission level (READ, WRITE, DESTRUCTIVE)
        parameters: JSON schema for parameters. If None, uses empty object.

    Example:
        @tool(
            description="List all locations in Homebox",
            permission=ToolPermission.READ,
            parameters={
                "type": "object",
                "properties": {
                    "filter_children": {
                        "type": "boolean",
                        "description": "If true, only return top-level locations",
                    }
                }
            }
        )
        async def list_locations(self, token: str, *, filter_children: bool = False):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._tool_metadata = ToolMetadata(
            description=description,
            permission=permission,
            parameters=parameters or {"type": "object", "properties": {}},
        )
        return wrapper
    return decorator


class HomeboxMCPTools:
    """Collection of MCP tools for Homebox operations.

    This class provides tool implementations that wrap HomeboxClient methods.
    Each tool method returns a ToolResult with standardized success/error handling.

    All tools require a valid Homebox auth token for execution.
    """

    def __init__(self, client: HomeboxClient):
        """Initialize with a HomeboxClient instance.

        Args:
            client: The HomeboxClient to use for API calls.
        """
        self.client = client

    # =========================================================================
    # READ-ONLY TOOLS (Phase A)
    # =========================================================================

    async def list_locations(
        self,
        token: str,
        *,
        filter_children: bool = False,
    ) -> ToolResult:
        """List all locations in Homebox.

        Args:
            token: Homebox auth token
            filter_children: If True, only return top-level locations

        Returns:
            ToolResult with list of location dicts
        """
        try:
            locations = await self.client.list_locations(
                token, filter_children=filter_children if filter_children else None
            )
            logger.debug(f"list_locations returned {len(locations)} locations")
            return ToolResult(success=True, data=locations)
        except Exception as e:
            logger.error(f"list_locations failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_location(
        self,
        token: str,
        *,
        location_id: str,
    ) -> ToolResult:
        """Get a specific location with its children.

        Args:
            token: Homebox auth token
            location_id: ID of the location to fetch

        Returns:
            ToolResult with location dict including children
        """
        try:
            location = await self.client.get_location(token, location_id)
            logger.debug(f"get_location returned location: {location.get('name', 'unknown')}")
            return ToolResult(success=True, data=location)
        except Exception as e:
            logger.error(f"get_location failed for {location_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def list_labels(
        self,
        token: str,
    ) -> ToolResult:
        """List all labels in Homebox.

        Args:
            token: Homebox auth token

        Returns:
            ToolResult with list of label dicts
        """
        try:
            labels = await self.client.list_labels(token)
            logger.debug(f"list_labels returned {len(labels)} labels")
            return ToolResult(success=True, data=labels)
        except Exception as e:
            logger.error(f"list_labels failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def list_items(
        self,
        token: str,
        *,
        location_id: str | None = None,
        label_ids: list[str] | None = None,
        page: int | None = None,
        page_size: int = 50,
        compact: bool = True,
    ) -> ToolResult:
        """List items with optional filtering and pagination.

        Args:
            token: Homebox auth token
            location_id: Optional location ID to filter by
            label_ids: Optional list of label IDs to filter by
            page: Optional page number (1-indexed)
            page_size: Number of items per page (default 50)
            compact: Return only essential fields by default (id, name, location,
                quantity). Set to False for full item details.

        Returns:
            ToolResult with list of item dicts
        """
        try:
            items = await self.client.list_items(
                token,
                location_id=location_id,
                label_ids=label_ids,
                page=page,
                page_size=page_size,
            )

            if compact:
                items = [_compact_item(item) for item in items]
                logger.debug(f"list_items returned {len(items)} items (compact mode)")
            else:
                logger.debug(f"list_items returned {len(items)} items")

            return ToolResult(success=True, data=items)
        except Exception as e:
            logger.error(f"list_items failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def search_items(
        self,
        token: str,
        *,
        query: str,
        limit: int = 50,
        compact: bool = True,
    ) -> ToolResult:
        """Search items by text query.

        Use this tool for semantic searches like "find rope", "items for building X",
        or any text-based search. More efficient than listing all items.

        Args:
            token: Homebox auth token
            query: Search query string (searches name, description, etc.)
            limit: Maximum number of results to return (default 50)
            compact: Return only essential fields by default (id, name, location,
                quantity). Set to False for full item details.

        Returns:
            ToolResult with list of matching item dicts
        """
        try:
            items = await self.client.search_items(token, query=query, limit=limit)

            if compact:
                items = [_compact_item(item) for item in items]
                logger.debug(f"search_items('{query}') returned {len(items)} items (compact mode)")
            else:
                logger.debug(f"search_items('{query}') returned {len(items)} items")

            return ToolResult(success=True, data=items)
        except Exception as e:
            logger.error(f"search_items failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_item(
        self,
        token: str,
        *,
        item_id: str,
    ) -> ToolResult:
        """Get full item details by ID.

        Args:
            token: Homebox auth token
            item_id: ID of the item to fetch

        Returns:
            ToolResult with full item dict
        """
        try:
            item = await self.client.get_item(token, item_id)
            logger.debug(f"get_item returned item: {item.get('name', 'unknown')}")
            return ToolResult(success=True, data=item)
        except Exception as e:
            logger.error(f"get_item failed for {item_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_statistics(
        self,
        token: str,
    ) -> ToolResult:
        """Get inventory statistics overview.

        Returns counts and totals without loading full item data.
        Use this for overview questions like "how many items" or "total inventory value".

        Args:
            token: Homebox auth token

        Returns:
            ToolResult with statistics dict containing:
            - totalItems: Count of all items
            - totalLocations: Count of locations
            - totalLabels: Count of labels
            - totalItemPrice: Sum of item prices
            - totalWithWarranty: Count of items with warranty
            - totalUsers: Count of users
        """
        try:
            stats = await self.client.get_statistics(token)
            logger.debug(f"get_statistics returned: {stats.get('totalItems', 0)} items")
            return ToolResult(success=True, data=stats)
        except Exception as e:
            logger.error(f"get_statistics failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_item_by_asset_id(
        self,
        token: str,
        *,
        asset_id: str,
    ) -> ToolResult:
        """Get item by its asset ID.

        Look up an item using its printed asset ID (e.g., "000-085").
        Useful for barcode scanning or when user provides an asset ID.

        Args:
            token: Homebox auth token
            asset_id: The asset ID to look up (e.g., "000-085")

        Returns:
            ToolResult with item dict
        """
        try:
            item = await self.client.get_item_by_asset_id(token, asset_id)
            logger.debug(
                f"get_item_by_asset_id({asset_id}) returned item: "
                f"{item.get('name', 'unknown')}"
            )
            return ToolResult(success=True, data=item)
        except Exception as e:
            logger.error(f"get_item_by_asset_id failed for {asset_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_location_tree(
        self,
        token: str,
        *,
        with_items: bool = False,
    ) -> ToolResult:
        """Get hierarchical location tree.

        Returns locations in a tree structure showing parent-child relationships.
        More efficient than multiple get_location calls when you need the hierarchy.

        Args:
            token: Homebox auth token
            with_items: If True, include items in the tree structure

        Returns:
            ToolResult with list of tree nodes (each with nested children)
        """
        try:
            tree = await self.client.get_location_tree(token, with_items=with_items)
            logger.debug(f"get_location_tree returned {len(tree)} top-level nodes")
            return ToolResult(success=True, data=tree)
        except Exception as e:
            logger.error(f"get_location_tree failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_statistics_by_location(
        self,
        token: str,
    ) -> ToolResult:
        """Get item counts grouped by location.

        Returns a list of locations with their item counts.
        Useful for analytics queries like "which location has the most items?"

        Args:
            token: Homebox auth token

        Returns:
            ToolResult with list of dicts (id, name, total)
        """
        try:
            stats = await self.client.get_statistics_by_location(token)
            logger.debug(f"get_statistics_by_location returned {len(stats)} locations")
            return ToolResult(success=True, data=stats)
        except Exception as e:
            logger.error(f"get_statistics_by_location failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_statistics_by_label(
        self,
        token: str,
    ) -> ToolResult:
        """Get item counts grouped by label.

        Returns a list of labels with their item counts.
        Useful for analytics queries like "how many items are tagged Electronics?"

        Args:
            token: Homebox auth token

        Returns:
            ToolResult with list of dicts (id, name, total)
        """
        try:
            stats = await self.client.get_statistics_by_label(token)
            logger.debug(f"get_statistics_by_label returned {len(stats)} labels")
            return ToolResult(success=True, data=stats)
        except Exception as e:
            logger.error(f"get_statistics_by_label failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_item_path(
        self,
        token: str,
        *,
        item_id: str,
    ) -> ToolResult:
        """Get the full hierarchical path of an item.

        Returns the location chain from root to the item's location.
        Useful for telling users exactly where to find an item.

        Args:
            token: Homebox auth token
            item_id: ID of the item

        Returns:
            ToolResult with list of path elements (id, name, type)
        """
        try:
            path = await self.client.get_item_path(token, item_id)
            logger.debug(f"get_item_path for {item_id} returned {len(path)} path elements")
            return ToolResult(success=True, data=path)
        except Exception as e:
            logger.error(f"get_item_path failed for {item_id}: {e}")
            return ToolResult(success=False, error=str(e))

    # =========================================================================
    # WRITE TOOLS (Phase D)
    # =========================================================================

    async def create_item(
        self,
        token: str,
        *,
        name: str,
        location_id: str,
        description: str = "",
        label_ids: list[str] | None = None,
    ) -> ToolResult:
        """Create a new item in Homebox.

        Args:
            token: Homebox auth token
            name: Name of the item
            location_id: ID of the location to place the item
            description: Optional description
            label_ids: Optional list of label IDs to apply

        Returns:
            ToolResult with created item data
        """
        try:
            from ..homebox.models import ItemCreate

            item_data = ItemCreate(
                name=name,
                location_id=location_id,
                description=description,
                label_ids=label_ids or [],
            )
            result = await self.client.create_item(token, item_data)
            logger.info(f"create_item created item: {result.get('name', 'unknown')}")
            return ToolResult(success=True, data=result)
        except Exception as e:
            logger.error(f"create_item failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def update_item(
        self,
        token: str,
        *,
        item_id: str,
        name: str | None = None,
        description: str | None = None,
        location_id: str | None = None,
    ) -> ToolResult:
        """Update an existing item.

        Args:
            token: Homebox auth token
            item_id: ID of the item to update
            name: Optional new name
            description: Optional new description
            location_id: Optional new location ID

        Returns:
            ToolResult with updated item data
        """
        try:
            # First get the current item to preserve fields
            current = await self.client.get_item(token, item_id)

            # Build update payload with only changed fields
            update_data = dict(current)
            if name is not None:
                update_data["name"] = name
            if description is not None:
                update_data["description"] = description
            if location_id is not None:
                update_data["location"] = {"id": location_id}

            result = await self.client.update_item(token, item_id, update_data)
            logger.info(f"update_item updated item: {result.get('name', 'unknown')}")
            return ToolResult(success=True, data=result)
        except Exception as e:
            logger.error(f"update_item failed for {item_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def delete_item(
        self,
        token: str,
        *,
        item_id: str,
    ) -> ToolResult:
        """Delete an item from Homebox.

        Args:
            token: Homebox auth token
            item_id: ID of the item to delete

        Returns:
            ToolResult with success status
        """
        try:
            await self.client.delete_item(token, item_id)
            logger.info(f"delete_item deleted item: {item_id}")
            return ToolResult(success=True, data={"deleted_id": item_id})
        except Exception as e:
            logger.error(f"delete_item failed for {item_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def create_location(
        self,
        token: str,
        *,
        name: str,
        description: str = "",
        parent_id: str | None = None,
    ) -> ToolResult:
        """Create a new location in Homebox.

        Args:
            token: Homebox auth token
            name: Name of the location
            description: Optional description
            parent_id: Optional parent location ID for nesting

        Returns:
            ToolResult with created location data
        """
        try:
            result = await self.client.create_location(
                token,
                name=name,
                description=description,
                parent_id=parent_id,
            )
            logger.info(f"create_location created location: {result.get('name', 'unknown')}")
            return ToolResult(success=True, data=result)
        except Exception as e:
            logger.error(f"create_location failed: {e}")
            return ToolResult(success=False, error=str(e))

    async def update_location(
        self,
        token: str,
        *,
        location_id: str,
        name: str | None = None,
        description: str | None = None,
        parent_id: str | None = _UNSET,
    ) -> ToolResult:
        """Update an existing location.

        Args:
            token: Homebox auth token
            location_id: ID of the location to update
            name: Optional new name
            description: Optional new description
            parent_id: New parent location ID, or None to make top-level

        Returns:
            ToolResult with updated location data
        """
        try:
            # First get the current location to preserve fields
            current = await self.client.get_location(token, location_id)

            # Determine parent_id: use provided value, or keep current if unset
            if parent_id is _UNSET:
                resolved_parent_id = current.get("parent", {}).get("id")
            else:
                resolved_parent_id = parent_id  # Could be None (make top-level)

            # Use current values for fields not being updated
            result = await self.client.update_location(
                token,
                location_id=location_id,
                name=name if name is not None else current.get("name", ""),
                description=(
                    description
                    if description is not None
                    else current.get("description", "")
                ),
                parent_id=resolved_parent_id,
            )
            logger.info(f"update_location updated location: {result.get('name', 'unknown')}")
            return ToolResult(success=True, data=result)
        except Exception as e:
            logger.error(f"update_location failed for {location_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def get_attachment(
        self,
        token: str,
        *,
        item_id: str,
        attachment_id: str,
    ) -> ToolResult:
        """Get an attachment's content by ID.

        Args:
            token: Homebox auth token
            item_id: ID of the item the attachment belongs to
            attachment_id: ID of the attachment to fetch

        Returns:
            ToolResult with attachment content (base64 encoded) and content type
        """
        try:
            content_bytes, content_type = await self.client.get_attachment(
                token, item_id, attachment_id
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
        except Exception as e:
            logger.error(f"get_attachment failed for {attachment_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def upload_attachment(
        self,
        token: str,
        *,
        item_id: str,
        file_base64: str,
        filename: str,
        mime_type: str = "image/jpeg",
        attachment_type: str = "photo",
    ) -> ToolResult:
        """Upload an attachment to an item.

        Args:
            token: Homebox auth token
            item_id: ID of the item to attach to
            file_base64: File content as base64 encoded string
            filename: Name for the uploaded file
            mime_type: MIME type of the file (default: image/jpeg)
            attachment_type: Type of attachment: 'photo', 'manual', 'warranty', etc.

        Returns:
            ToolResult with created attachment data
        """
        try:
            file_bytes = base64.b64decode(file_base64)
        except binascii.Error as e:
            logger.error(f"upload_attachment invalid base64: {e}")
            return ToolResult(success=False, error=f"Invalid base64 encoding: {e}")

        try:
            result = await self.client.upload_attachment(
                token,
                item_id=item_id,
                file_bytes=file_bytes,
                filename=filename,
                mime_type=mime_type,
                attachment_type=attachment_type,
            )
            logger.info(f"upload_attachment uploaded {filename} to item {item_id}")
            return ToolResult(success=True, data=result)
        except Exception as e:
            logger.error(f"upload_attachment failed for item {item_id}: {e}")
            return ToolResult(success=False, error=str(e))

    async def ensure_asset_ids(
        self,
        token: str,
    ) -> ToolResult:
        """Ensure all items have asset IDs assigned.

        Assigns sequential asset IDs to all items that don't currently have one.
        This is idempotent - items that already have asset IDs are not affected.

        Args:
            token: Homebox auth token

        Returns:
            ToolResult with count of items that were assigned asset IDs
        """
        try:
            count = await self.client.ensure_asset_ids(token)
            logger.info(f"ensure_asset_ids assigned IDs to {count} items")
            return ToolResult(success=True, data={"items_updated": count})
        except Exception as e:
            logger.error(f"ensure_asset_ids failed: {e}")
            return ToolResult(success=False, error=str(e))

    @classmethod
    def get_tool_metadata(cls) -> dict[str, dict[str, Any]]:
        """Return metadata for all available tools.

        This method collects metadata from two sources:
        1. Methods decorated with @tool (preferred, co-located with implementation)
        2. Static dictionary below (legacy, for gradual migration)

        The decorator-based approach is preferred as it co-locates metadata
        with the implementation, making it easier to keep them in sync.

        Returns:
            Dict mapping tool names to their metadata including:
            - description: Human-readable description
            - permission: ToolPermission level
            - parameters: JSON schema for tool parameters
        """
        # Collect from decorated methods
        metadata: dict[str, dict[str, Any]] = {}
        for name in dir(cls):
            if name.startswith("_"):
                continue
            method = getattr(cls, name, None)
            if method and hasattr(method, "_tool_metadata"):
                meta: ToolMetadata = method._tool_metadata
                metadata[name] = {
                    "description": meta.description,
                    "permission": meta.permission,
                    "parameters": meta.parameters,
                }

        # Add/override with static definitions for non-decorated methods
        # This allows gradual migration from static dict to decorators
        static_metadata = {
            "list_locations": {
                "description": "List all locations in Homebox inventory",
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter_children": {
                            "type": "boolean",
                            "description": "If true, only return top-level locations",
                            "default": False,
                        },
                    },
                },
            },
            "get_location": {
                "description": "Get a specific location with its child locations",
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location_id": {
                            "type": "string",
                            "description": "The ID of the location to fetch",
                        },
                    },
                    "required": ["location_id"],
                },
            },
            "list_labels": {
                "description": "List all labels available for categorizing items",
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "list_items": {
                "description": (
                    "List items in the inventory with optional filtering and "
                    "pagination. For text-based searches, prefer using search_items "
                    "instead."
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location_id": {
                            "type": "string",
                            "description": "Optional location ID to filter items by",
                        },
                        "label_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of label IDs to filter items by",
                        },
                        "page": {
                            "type": "integer",
                            "description": "Optional page number (1-indexed) for pagination",
                        },
                        "page_size": {
                            "type": "integer",
                            "description": (
                                "Number of items per page "
                                "(default 50, max recommended 100)"
                            ),
                            "default": 50,
                        },
                        "compact": {
                            "type": "boolean",
                            "description": (
                                "If true, return only essential fields "
                                "(id, name, location, quantity) to reduce payload "
                                "size. Use when you don't need full item details."
                            ),
                            "default": True,
                        },
                    },
                },
            },
            "search_items": {
                "description": (
                    "Search items by text query. Use this for semantic searches "
                    "like 'find rope', 'items for building X', or any keyword-based "
                    "search. More efficient than listing all items when you know "
                    "what you're looking for."
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Search query string (searches item names, "
                                "descriptions, and other text fields)"
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 50)",
                            "default": 50,
                        },
                        "compact": {
                            "type": "boolean",
                            "description": (
                                "If true, return only essential fields "
                                "(id, name, location, quantity) to reduce payload "
                                "size. Use when you don't need full item details."
                            ),
                            "default": True,
                        },
                    },
                    "required": ["query"],
                },
            },
            "get_item": {
                "description": "Get full details of a specific item",
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "The ID of the item to fetch",
                        },
                    },
                    "required": ["item_id"],
                },
            },
            "get_statistics": {
                "description": (
                    "Get inventory overview statistics (counts and totals). "
                    "Use this for questions like 'how many items do I have?' or "
                    "'what's the total value?' instead of loading all items."
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "get_item_by_asset_id": {
                "description": (
                    "Get an item by its asset ID (e.g., '000-085'). Use this when "
                    "the user provides an asset ID or for barcode scanning scenarios."
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "asset_id": {
                            "type": "string",
                            "description": "The asset ID to look up (e.g., '000-085')",
                        },
                    },
                    "required": ["asset_id"],
                },
            },
            "get_location_tree": {
                "description": (
                    "Get hierarchical location tree showing parent-child "
                    "relationships. Use this to understand the location organization "
                    "structure."
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "with_items": {
                            "type": "boolean",
                            "description": "If true, include items in the tree structure",
                            "default": False,
                        },
                    },
                },
            },
            "get_statistics_by_location": {
                "description": (
                    "Get item counts grouped by location. Use this for analytics "
                    "queries like 'which location has the most items?'"
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "get_statistics_by_label": {
                "description": (
                    "Get item counts grouped by label. Use this for analytics "
                    "queries like 'how many items are tagged Electronics?'"
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            "get_item_path": {
                "description": (
                    "Get the full hierarchical path of an item (location chain from "
                    "root to item). Use this to tell users exactly where to find an "
                    "item."
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "The ID of the item",
                        },
                    },
                    "required": ["item_id"],
                },
            },
            # Write tools (require approval)
            "create_item": {
                "description": "Create a new item in the inventory",
                "permission": ToolPermission.WRITE,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the item",
                        },
                        "location_id": {
                            "type": "string",
                            "description": "ID of the location to place the item",
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional description of the item",
                        },
                        "label_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of label IDs to apply",
                        },
                    },
                    "required": ["name", "location_id"],
                },
            },
            "update_item": {
                "description": "Update an existing item's name, description, or location",
                "permission": ToolPermission.WRITE,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "ID of the item to update",
                        },
                        "name": {
                            "type": "string",
                            "description": "New name for the item",
                        },
                        "description": {
                            "type": "string",
                            "description": "New description for the item",
                        },
                        "location_id": {
                            "type": "string",
                            "description": "New location ID to move the item to",
                        },
                    },
                    "required": ["item_id"],
                },
            },
            "delete_item": {
                "description": "Permanently delete an item from the inventory",
                "permission": ToolPermission.DESTRUCTIVE,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "ID of the item to delete",
                        },
                    },
                    "required": ["item_id"],
                },
            },
            # Location write tools
            "create_location": {
                "description": "Create a new location in the inventory",
                "permission": ToolPermission.WRITE,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the location",
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional description of the location",
                        },
                        "parent_id": {
                            "type": "string",
                            "description": "Optional parent location ID for nesting",
                        },
                    },
                    "required": ["name"],
                },
            },
            "update_location": {
                "description": (
                    "Update an existing location's name, description, or parent. "
                    "Use this to rename locations, add/edit descriptions, "
                    "or reorganize the location hierarchy."
                ),
                "permission": ToolPermission.WRITE,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location_id": {
                            "type": "string",
                            "description": "ID of the location to update",
                        },
                        "name": {
                            "type": "string",
                            "description": "New name for the location",
                        },
                        "description": {
                            "type": "string",
                            "description": "New description for the location",
                        },
                        "parent_id": {
                            "type": "string",
                            "description": "New parent location ID (or null to make top-level)",
                        },
                    },
                    "required": ["location_id"],
                },
            },
            # Attachment tools
            "get_attachment": {
                "description": (
                    "Get an attachment's content by ID. Returns the file as "
                    "base64 encoded data along with content type."
                ),
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "ID of the item the attachment belongs to",
                        },
                        "attachment_id": {
                            "type": "string",
                            "description": "ID of the attachment to fetch",
                        },
                    },
                    "required": ["item_id", "attachment_id"],
                },
            },
            "upload_attachment": {
                "description": (
                    "Upload an attachment (image, manual, etc.) to an item. "
                    "File content must be base64 encoded."
                ),
                "permission": ToolPermission.WRITE,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_id": {
                            "type": "string",
                            "description": "ID of the item to attach to",
                        },
                        "file_base64": {
                            "type": "string",
                            "description": "File content as base64 encoded string",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Name for the uploaded file",
                        },
                        "mime_type": {
                            "type": "string",
                            "description": "MIME type of the file (default: image/jpeg)",
                            "default": "image/jpeg",
                        },
                        "attachment_type": {
                            "type": "string",
                            "description": (
                                "Type of attachment: 'photo', 'manual', "
                                "'warranty', 'receipt', 'attachment'"
                            ),
                            "default": "photo",
                        },
                    },
                    "required": ["item_id", "file_base64", "filename"],
                },
            },
            # Action tools
            "ensure_asset_ids": {
                "description": (
                    "Ensure all items have asset IDs assigned. Assigns sequential "
                    "asset IDs to items that don't have one. Idempotent - existing "
                    "asset IDs are not changed."
                ),
                "permission": ToolPermission.WRITE,
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }

        # Merge: static_metadata fills gaps for non-decorated methods
        # Decorated methods take precedence (already in metadata)
        for name, meta in static_metadata.items():
            if name not in metadata:
                metadata[name] = meta

        return metadata
