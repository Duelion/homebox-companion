"""Core types for MCP tool definitions.

This module contains the shared types used across MCP tool implementations:
- ToolPermission: Enum for tool permission levels
- ToolParams: Base class for tool parameter models
- ToolResult: Standard result wrapper for tool execution
- Tool: Protocol defining the tool contract
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ..homebox.client import HomeboxClient

__all__ = [
    "ToolPermission",
    "ToolParams",
    "ToolResult",
    "Tool",
    "MAX_RESULT_ITEMS",
]

# Truncation limits for tool results (reduces context window usage)
MAX_RESULT_ITEMS = 25  # Maximum items in list results


class ToolPermission(str, Enum):
    """Permission level required to execute a tool.

    READ: Safe to auto-execute, no side effects
    WRITE: Modifies data, requires user approval
    DESTRUCTIVE: Deletes data, requires approval + confirmation
    """

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ToolParams(BaseModel):
    """Base class for tool parameter models.

    All tool Params inner classes should inherit from this to ensure
    consistent configuration (extra="forbid" catches typos in param names).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",  # Reject unknown parameters
    )


class ToolResult(BaseModel):
    """Standard result wrapper for tool execution.

    Attributes:
        success: Whether the operation succeeded
        data: The result data (on success) or None
        error: Error message (on failure) or None
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

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


@runtime_checkable
class Tool(Protocol):
    """Protocol defining the tool contract.

    All tool implementations must satisfy this protocol by providing:
    - name: Unique identifier for the tool
    - description: Human-readable description
    - permission: Required permission level
    - Params: Pydantic model class for parameter validation
    - execute: Async method to perform the tool's action
    """

    name: str
    description: str
    permission: ToolPermission
    Params: type[BaseModel]

    async def execute(
        self,
        client: HomeboxClient,
        token: str,
        params: BaseModel,
    ) -> ToolResult:
        """Execute the tool with validated parameters.

        Args:
            client: HomeboxClient instance for API calls
            token: Authentication token for Homebox
            params: Validated parameters (instance of self.Params)

        Returns:
            ToolResult with success/error status and data
        """
        ...
