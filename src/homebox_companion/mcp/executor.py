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
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from loguru import logger
from pydantic import ValidationError

from ..core.exceptions import HomeboxCompanionError
from ..homebox.client import HomeboxClient, HomeboxGateway
from .tools import get_tools
from .types import DisplayInfo, Tool, ToolPermission, ToolResult, get_action_type_from_tool_name

# Cache TTL for tool schemas (5 minutes)
_SCHEMA_CACHE_TTL = 300


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    """Request-owned resources used for one tool invocation."""

    client: Any
    token: str

    @classmethod
    def for_gateway(cls, gateway: HomeboxGateway) -> ToolExecutionContext:
        """Adapt token-argument tools to an immutable bound gateway."""
        return cls(client=_GatewayToolClient(gateway), token="<request-bound>")


class _GatewayToolClient:
    """Thin compatibility adapter for tools that still accept a token argument."""

    __slots__ = ("_gateway",)

    def __init__(self, gateway: HomeboxGateway) -> None:
        self._gateway = gateway

    def __getattr__(self, name: str) -> Any:
        target = getattr(self._gateway, name)
        if not callable(target):
            return target

        async def bound(_token: str, *args: Any, **kwargs: Any) -> Any:
            return await target(*args, **kwargs)

        return bound


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

    def __init__(self, client: HomeboxClient | HomeboxGateway | None = None):
        """Initialize the executor with a Homebox client.

        Args:
            client: HomeboxClient instance for tool API calls.
        """
        self._gateway: HomeboxGateway | None
        self._client: HomeboxClient | None
        if isinstance(client, HomeboxGateway):
            self._gateway = client
            self._client = client.transport_client
        else:
            self._gateway = None
            self._client = client
        self._schema_cache: tuple[list[dict[str, Any]], float] | None = None

    @property
    def client(self) -> HomeboxClient:
        """Get the Homebox client."""
        if self._client is None:
            raise RuntimeError("Tool execution requires a request context")
        return self._client

    @property
    def execution_token(self) -> str | None:
        """Credential of a request-bound gateway, unavailable on legacy executors."""
        if self._gateway is None:
            return None
        return self._gateway.access.credential.get_secret_value()

    @property
    def identity_scope(self) -> str | None:
        """Verified identity scope carried by a request-bound gateway."""
        return self._gateway.access.identity_scope if self._gateway else None

    @property
    def group_id(self) -> str | None:
        """Effective Homebox group carried by a request-bound gateway."""
        return self._gateway.access.group_id if self._gateway else None

    def bind(self, gateway: HomeboxGateway) -> BoundToolExecutor:
        """Bind request access while retaining this executor's shared caches."""
        return BoundToolExecutor(self, gateway)

    @cached_property
    def _tools_by_name(self) -> dict[str, Tool]:
        """Lazy-loaded tool lookup table."""
        tools = get_tools()
        result = {t.name: t for t in tools}
        logger.trace(f"ToolExecutor discovered {len(result)} tools")
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

    def get_tool_schemas(
        self,
        include_write: bool = True,
        include_token: bool = False,
    ) -> list[dict[str, Any]]:
        """Get tool definitions in OpenAI/LiteLLM function calling format.

        Uses instance-level caching with TTL to avoid rebuilding schemas.

        Args:
            include_write: If True, include WRITE and DESTRUCTIVE tools.
                          If False, only include READ tools.
            include_token: If True, include 'token' as a required parameter
                          in each schema. Used for MCP protocol where clients
                          need to know about authentication requirements.

        Returns:
            List of tool schema dicts suitable for LLM function calling.
        """
        import copy

        # Check instance-level cache
        if self._schema_cache and (time.time() - self._schema_cache[1]) < _SCHEMA_CACHE_TTL:
            all_schemas = self._schema_cache[0]
        else:
            # Rebuild cache
            all_schemas = []
            for tool in self._tools_by_name.values():
                all_schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.Params.model_json_schema(),
                        },
                    }
                )
            self._schema_cache = (all_schemas, time.time())
            logger.debug(f"Built and cached {len(all_schemas)} tool schemas")

        # Filter by permission if needed
        if include_write:
            schemas = all_schemas
        else:
            read_tool_names = {t.name for t in self._tools_by_name.values() if t.permission == ToolPermission.READ}
            schemas = [s for s in all_schemas if s["function"]["name"] in read_tool_names]

        # Deep copy to prevent cache mutation
        result = copy.deepcopy(schemas)

        # Inject token parameter for MCP protocol compatibility
        if include_token:
            for schema in result:
                params = schema["function"]["parameters"]
                if "properties" not in params:
                    params["properties"] = {}
                params["properties"]["token"] = {
                    "type": "string",
                    "description": "Homebox authentication token (required)",
                }
                if "required" not in params:
                    params["required"] = []
                if "token" not in params["required"]:
                    params["required"].append("token")

        return result

    async def get_display_info(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        token: str,
        *,
        context: ToolExecutionContext | None = None,
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
        # Derive action type from tool name convention (create_*, update_*, delete_*)
        action_type = get_action_type_from_tool_name(tool_name)

        target_name: str | None = None
        item_name: str | None = None  # Kept for backward compatibility
        asset_id: str | None = None
        location: str | None = None
        client = context.client if context else self.client

        try:
            # Item operations
            if tool_name in ("delete_item", "update_item") and "item_id" in tool_args:
                item = await client.get_item(token, tool_args["item_id"])
                item_name = item.get("name")
                target_name = item_name
                if item.get("assetId"):
                    asset_id = item.get("assetId")
                if tool_name == "delete_item" and item.get("parent"):
                    location = item["parent"].get("name")

            elif tool_name == "create_item":
                if "name" in tool_args:
                    item_name = tool_args["name"]
                    target_name = item_name
                if "location_id" in tool_args:
                    try:
                        loc = await client.get_location(token, tool_args["location_id"])
                        location = loc.get("name")
                    except Exception as e:
                        logger.debug(f"Location lookup failed: {e}")

            # Location operations
            elif tool_name in ("update_location", "delete_location") and "location_id" in tool_args:
                loc = await client.get_location(token, tool_args["location_id"])
                target_name = loc.get("name")

            elif tool_name == "create_location":
                target_name = tool_args.get("name")

            # Tag operations
            elif tool_name in ("update_tag", "delete_tag") and "tag_id" in tool_args:
                tag = await client.get_tag(token, tool_args["tag_id"])
                target_name = tag.get("name")

            elif tool_name == "create_tag":
                target_name = tool_args.get("name")

        except Exception as e:
            logger.debug(f"Failed to fetch display info for {tool_name}: {e}")

        # Log successful display info resolution
        if target_name:
            logger.debug(f"Resolved display info for {tool_name}: target_name='{target_name}'")

        return DisplayInfo(
            action_type=action_type,
            target_name=target_name,
            item_name=item_name,
            asset_id=asset_id,
            location=location,
        )

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

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        token: str | None = None,
        *,
        context: ToolExecutionContext | None = None,
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
        client = context.client if context else self.client
        effective_token = context.token if context else (token or self.execution_token)
        if not effective_token:
            return ToolResult(success=False, error="Tool execution requires Homebox access")
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
            result = await tool.execute(client, effective_token, validated_params)
            return result
        except HomeboxCompanionError:
            # Preserve centralized safe status/code handling for HTTP and SSE.
            raise
        except Exception as e:
            logger.exception(f"Tool {tool_name} execution failed")
            return ToolResult(success=False, error=str(e))


class BoundToolExecutor(ToolExecutor):
    """Request binding over a shared stateless registry/schema executor."""

    def __init__(self, shared: ToolExecutor, gateway: HomeboxGateway) -> None:
        super().__init__(gateway)
        self._shared = shared
        self._context = ToolExecutionContext.for_gateway(gateway)

    def get_tool(self, name: str) -> Tool | None:
        return self._shared.get_tool(name)

    def list_tools(self, permission_filter: ToolPermission | None = None) -> list[Tool]:
        return self._shared.list_tools(permission_filter)

    def get_tool_schemas(
        self,
        include_write: bool = True,
        include_token: bool = False,
    ) -> list[dict[str, Any]]:
        return self._shared.get_tool_schemas(include_write, include_token)

    def requires_approval(self, tool_name: str) -> bool:
        return self._shared.requires_approval(tool_name)

    async def get_display_info(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        token: str,
        *,
        context: ToolExecutionContext | None = None,
    ) -> DisplayInfo:
        return await self._shared.get_display_info(
            tool_name,
            tool_args,
            token,
            context=context or self._context,
        )

    async def execute(
        self,
        tool_name: str,
        params: dict[str, Any],
        token: str | None = None,
        *,
        context: ToolExecutionContext | None = None,
    ) -> ToolResult:
        return await self._shared.execute(
            tool_name,
            params,
            token,
            context=context or self._context,
        )
