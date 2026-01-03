"""Tool execution service for MCP operations.

This module provides a centralized service for tool discovery and execution,
used by both the chat orchestrator and the MCP server endpoints.

The ToolExecutor is the single source of truth for:
- Tool discovery and lookup
- Tool schema generation (for LLM function calling)
- Permission checking
- Parameter validation and execution
"""

from __future__ import annotations

import time
from functools import cached_property
from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import ValidationError

from .tools import get_tools
from .types import DisplayInfo, Tool, ToolPermission, ToolResult

if TYPE_CHECKING:
    from ..homebox.client import HomeboxClient


# Cache TTL for tool schemas (5 minutes)
_SCHEMA_CACHE_TTL = 300


class ToolExecutor:
    """Single entry point for tool discovery and execution.

    This service consolidates all tool-related logic that was previously
    scattered across the chat orchestrator and API routers. It provides:

    - Tool discovery via `list_tools()` and `get_tool()`
    - Schema generation for LLM function calling via `get_tool_schemas()`
    - Permission checking via `requires_approval()`
    - Validated execution via `execute()`

    Example:
        >>> executor = ToolExecutor(client)
        >>> if executor.requires_approval("delete_item"):
        ...     # Queue for approval
        ... else:
        ...     result = await executor.execute("list_items", {"page": 1}, token)
    """

    def __init__(self, client: HomeboxClient):
        """Initialize the executor with a Homebox client.

        Args:
            client: HomeboxClient instance for tool API calls.
        """
        self._client = client
        self._schema_cache: tuple[list[dict[str, Any]], float] | None = None

    @property
    def client(self) -> HomeboxClient:
        """Get the Homebox client."""
        return self._client

    @cached_property
    def _tools_by_name(self) -> dict[str, Tool]:
        """Lazy-loaded tool lookup table."""
        tools = get_tools()
        result = {t.name: t for t in tools}
        logger.debug(f"ToolExecutor discovered {len(result)} tools")
        return result

    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: The tool name to look up.

        Returns:
            The Tool instance or None if not found.
        """
        return self._tools_by_name.get(name)

    def list_tools(
        self,
        permission_filter: ToolPermission | None = None,
    ) -> list[Tool]:
        """List all available tools, optionally filtered by permission.

        Args:
            permission_filter: If provided, only return tools with this permission.

        Returns:
            List of Tool instances.
        """
        tools = list(self._tools_by_name.values())
        if permission_filter is not None:
            tools = [t for t in tools if t.permission == permission_filter]
        return tools

    def get_tool_schemas(self, include_write: bool = True) -> list[dict[str, Any]]:
        """Get tool definitions in OpenAI/LiteLLM function calling format.

        Uses instance-level caching with TTL to avoid rebuilding schemas.

        Args:
            include_write: If True, include WRITE and DESTRUCTIVE tools.
                          If False, only include READ tools.

        Returns:
            List of tool schema dicts suitable for LLM function calling.
        """
        # Check instance-level cache
        if self._schema_cache and (time.time() - self._schema_cache[1]) < _SCHEMA_CACHE_TTL:
            all_schemas = self._schema_cache[0]
        else:
            # Rebuild cache
            all_schemas = []
            for tool in self._tools_by_name.values():
                all_schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.Params.model_json_schema(),
                    },
                })
            self._schema_cache = (all_schemas, time.time())
            logger.debug(f"Built and cached {len(all_schemas)} tool schemas")

        if include_write:
            return list(all_schemas)  # Return copy to prevent cache mutation

        # Filter to READ-only tools
        read_tool_names = {
            t.name for t in self._tools_by_name.values()
            if t.permission == ToolPermission.READ
        }
        return [s for s in all_schemas if s["function"]["name"] in read_tool_names]

    def invalidate_cache(self) -> None:
        """Invalidate all caches including tool discovery and schema cache.

        Useful for testing or when tools are modified at runtime.
        """
        self._schema_cache = None
        # Clear the cached_property by removing it from instance __dict__
        self.__dict__.pop("_tools_by_name", None)
        logger.debug("Tool executor caches invalidated")

    async def get_display_info(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        token: str,
    ) -> DisplayInfo:
        """Fetch human-readable info for approval UI.

        Encapsulates client access for display purposes, avoiding
        abstraction leaks from the orchestrator.

        Args:
            tool_name: Name of the tool.
            tool_args: Tool arguments.
            token: Homebox auth token.

        Returns:
            DisplayInfo with human-readable details.
        """
        item_name: str | None = None
        asset_id: str | None = None
        location: str | None = None

        try:
            if tool_name in ("delete_item", "update_item") and "item_id" in tool_args:
                item = await self._client.get_item(token, tool_args["item_id"])
                item_name = item.get("name")
                if item.get("assetId"):
                    asset_id = item.get("assetId")
                if tool_name == "delete_item" and item.get("location"):
                    location = item["location"].get("name")

            elif tool_name == "create_item":
                if "name" in tool_args:
                    item_name = tool_args["name"]
                if "location_id" in tool_args:
                    try:
                        loc = await self._client.get_location(token, tool_args["location_id"])
                        location = loc.get("name")
                    except Exception as e:
                        logger.debug(f"Location lookup failed: {e}")

        except Exception as e:
            logger.debug(f"Failed to fetch display info for {tool_name}: {e}")

        return DisplayInfo(item_name=item_name, asset_id=asset_id, location=location)

    def requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval before execution.

        Args:
            tool_name: The name of the tool to check.

        Returns:
            True if the tool requires approval (WRITE, DESTRUCTIVE, or unknown).
            False only for known READ tools.

        Note:
            Unknown tools return True (fail-safe) - they should be caught
            and handled as errors before execution, but if they somehow
            reach execution, requiring approval adds a safety layer.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return True  # Fail-safe: unknown tools require approval
        return tool.permission in (ToolPermission.WRITE, ToolPermission.DESTRUCTIVE)

    def get_permission(self, tool_name: str) -> ToolPermission | None:
        """Get the permission level for a tool.

        Args:
            tool_name: The name of the tool.

        Returns:
            The ToolPermission or None if tool not found.
        """
        tool = self.get_tool(tool_name)
        return tool.permission if tool else None

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        token: str,
    ) -> ToolResult:
        """Execute a tool with validated parameters.

        This method handles:
        1. Tool lookup
        2. Parameter validation via Pydantic
        3. Tool execution
        4. Error handling and result wrapping

        Args:
            tool_name: Name of the tool to execute.
            params: Raw parameters dict (will be validated).
            token: Homebox authentication token.

        Returns:
            ToolResult with success/error status and data.
        """
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"Attempted to execute unknown tool: {tool_name}")
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

        # Validate parameters with Pydantic
        try:
            validated_params = tool.Params(**params)
        except ValidationError as e:
            logger.warning(f"Tool {tool_name} parameter validation failed: {e}")
            return ToolResult(success=False, error=f"Invalid parameters: {e}")

        # Execute the tool
        logger.info(f"Executing tool: {tool_name}")
        try:
            result = await tool.execute(self._client, token, validated_params)
            return result
        except Exception as e:
            logger.exception(f"Tool {tool_name} execution failed")
            return ToolResult(success=False, error=str(e))

    async def execute_if_allowed(
        self,
        tool_name: str,
        params: dict[str, Any],
        token: str,
        allow_write: bool = False,
    ) -> ToolResult | None:
        """Execute a tool only if it doesn't require approval (or write is allowed).

        This is a convenience method for the chat flow where READ tools are
        auto-executed and WRITE tools are queued for approval.

        Args:
            tool_name: Name of the tool to execute.
            params: Raw parameters dict.
            token: Homebox authentication token.
            allow_write: If True, execute WRITE/DESTRUCTIVE tools too.

        Returns:
            ToolResult if executed, None if tool requires approval and
            allow_write is False.
        """
        if not allow_write and self.requires_approval(tool_name):
            return None
        return await self.execute(tool_name, params, token)
