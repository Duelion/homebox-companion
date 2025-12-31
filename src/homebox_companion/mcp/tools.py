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

from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger

from ..homebox.client import HomeboxClient


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
        """Convert to dictionary for MCP response."""
        if self.success:
            return {"success": True, "data": self.data}
        return {"success": False, "error": self.error}


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
    ) -> ToolResult:
        """List items, optionally filtered by location.
        
        Args:
            token: Homebox auth token
            location_id: Optional location ID to filter by
            
        Returns:
            ToolResult with list of item dicts
        """
        try:
            items = await self.client.list_items(token, location_id=location_id)
            logger.debug(f"list_items returned {len(items)} items")
            return ToolResult(success=True, data=items)
        except Exception as e:
            logger.error(f"list_items failed: {e}")
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
            from ..homebox.schemas import ItemCreate
            
            item_data = ItemCreate(
                name=name,
                locationId=location_id,
                description=description,
                labelIds=label_ids or [],
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

    @classmethod
    def get_tool_metadata(cls) -> dict[str, dict[str, Any]]:
        """Return metadata for all available tools.
        
        This metadata is used by the MCP server to register tools and
        by the approval system to determine permission requirements.
        
        Returns:
            Dict mapping tool names to their metadata including:
            - description: Human-readable description
            - permission: ToolPermission level
            - parameters: JSON schema for tool parameters
        """
        return {
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
                "description": "List items in the inventory, optionally filtered by location",
                "permission": ToolPermission.READ,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location_id": {
                            "type": "string",
                            "description": "Optional location ID to filter items by",
                        },
                    },
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
        }
