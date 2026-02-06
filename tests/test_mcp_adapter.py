"""Unit tests for MCP Protocol adapter.

These tests verify the MCP adapter correctly wraps ToolExecutor.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homebox_companion.mcp.types import ToolResult

pytestmark = pytest.mark.unit


class TestHandleListTools:
    """Tests for handle_list_tools function."""

    @pytest.mark.asyncio
    async def test_returns_all_tools_with_schemas(self):
        """handle_list_tools should return all tools with inputSchema."""
        from server.mcp_adapter import handle_list_tools

        tools = await handle_list_tools()

        # Should return a non-empty list of tools
        assert len(tools) > 0
        assert len(tools) >= 20  # We have ~24 tools

        # Each tool should have required fields
        for tool in tools:
            assert tool.name
            assert tool.description
            assert tool.inputSchema
            assert isinstance(tool.inputSchema, dict)

    @pytest.mark.asyncio
    async def test_schema_has_required_json_schema_fields(self):
        """Each inputSchema should be a valid JSON schema."""
        from server.mcp_adapter import handle_list_tools

        tools = await handle_list_tools()

        for tool in tools:
            schema = tool.inputSchema
            # Should have type field
            assert "type" in schema
            assert schema["type"] == "object"
            # Should have properties for tools with parameters
            # (some tools may have no required params)


class TestHandleCallTool:
    """Tests for handle_call_tool function."""

    @pytest.mark.asyncio
    async def test_returns_error_when_token_not_configured(self):
        """Should return error when HBC_MCP_TOKEN is empty."""
        from server.mcp_adapter import handle_call_tool

        # Patch settings to have no token
        with patch("server.mcp_adapter.settings") as mock_settings:
            mock_settings.mcp_token = ""
            mock_settings.api_url = "http://test"

            result = await handle_call_tool("list_items", {})

        assert len(result) == 1
        assert "HBC_MCP_TOKEN not configured" in result[0].text

    @pytest.mark.asyncio
    async def test_delegates_to_executor_and_returns_json(self):
        """Should delegate to ToolExecutor and return JSON result."""
        from server.mcp_adapter import handle_call_tool

        mock_result = ToolResult(success=True, data={"items": []})

        with (
            patch("server.mcp_adapter.settings") as mock_settings,
            patch("server.mcp_adapter._get_executor") as mock_get_executor,
        ):
            mock_settings.mcp_token = "test-token"
            mock_settings.api_url = "http://test"

            mock_executor = MagicMock()
            mock_executor.execute = AsyncMock(return_value=mock_result)
            mock_get_executor.return_value = mock_executor

            result = await handle_call_tool("list_items", {"page": 1})

        # Should call executor with correct args
        mock_executor.execute.assert_called_once_with("list_items", {"page": 1}, "test-token")

        # Should return JSON text content
        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["success"] is True
        assert parsed["data"] == {"items": []}

    @pytest.mark.asyncio
    async def test_handles_none_arguments(self):
        """Should handle None arguments (MCP SDK passes None when no args)."""
        from server.mcp_adapter import handle_call_tool

        mock_result = ToolResult(success=True, data={"items": []})

        with (
            patch("server.mcp_adapter.settings") as mock_settings,
            patch("server.mcp_adapter._get_executor") as mock_get_executor,
        ):
            mock_settings.mcp_token = "test-token"
            mock_settings.api_url = "http://test"

            mock_executor = MagicMock()
            mock_executor.execute = AsyncMock(return_value=mock_result)
            mock_get_executor.return_value = mock_executor

            # Pass None as arguments (as MCP SDK does)
            result = await handle_call_tool("list_items", None)

        # Should call executor with empty dict, not None
        mock_executor.execute.assert_called_once_with("list_items", {}, "test-token")

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_tool(self):
        """Should return error result for unknown tool."""
        from server.mcp_adapter import handle_call_tool

        with patch("server.mcp_adapter.settings") as mock_settings:
            mock_settings.mcp_token = "test-token"
            mock_settings.api_url = "http://test"

            result = await handle_call_tool("nonexistent_tool", {})

        assert len(result) == 1
        parsed = json.loads(result[0].text)
        assert parsed["success"] is False
        assert "Unknown tool" in parsed["error"]
