"""Base class for AI-powered tools.

This module defines the abstract interface that all tools should implement.
This allows for consistent patterns when adding new AI-powered features
to the companion app.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for AI-powered companion tools.

    All tools should inherit from this class and implement the required
    methods. This ensures a consistent interface for tool registration
    and execution.

    Example:
        class LocationDescriber(BaseTool):
            @property
            def name(self) -> str:
                return "location_describer"

            @property
            def description(self) -> str:
                return "Generate descriptions for locations based on their contents"

            async def execute(self, location_id: str, token: str) -> dict:
                # Implementation here
                pass
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique identifier for this tool.

        This is used for routing API requests and identifying the tool
        in configuration and logs.

        Returns:
            A string identifier (e.g., 'vision', 'location_describer').
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Return a human-readable description of what this tool does.

        Returns:
            A description string for documentation and UI purposes.
        """
        pass

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool's main functionality.

        This is the primary entry point for tool execution. The signature
        will vary depending on what the tool does.

        Returns:
            Tool-specific result data.
        """
        pass





