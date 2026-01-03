"""Unit tests for ToolExecutor service.

These tests verify the centralized tool execution service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homebox_companion.mcp.executor import ToolExecutor
from homebox_companion.mcp.types import ToolPermission


class TestToolExecutor:
    """Tests for ToolExecutor class."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock HomeboxClient."""
        client = MagicMock()
        client.list_locations = AsyncMock(
            return_value=[{"id": "loc1", "name": "Test Location"}]
        )
        client.list_items = AsyncMock(return_value=[])
        client.list_labels = AsyncMock(return_value=[])
        client.get_item = AsyncMock(
            return_value={"id": "item1", "name": "Test Item"}
        )
        return client

    @pytest.fixture
    def executor(self, mock_client: MagicMock) -> ToolExecutor:
        """Create a ToolExecutor with mocked client."""
        return ToolExecutor(mock_client)

    def test_get_tool_returns_tool_by_name(self, executor: ToolExecutor):
        """get_tool should return tool instance for valid name."""
        tool = executor.get_tool("list_locations")

        assert tool is not None
        assert tool.name == "list_locations"

    def test_get_tool_returns_none_for_unknown(self, executor: ToolExecutor):
        """get_tool should return None for unknown tool name."""
        tool = executor.get_tool("nonexistent_tool")

        assert tool is None

    def test_list_tools_returns_all_tools(self, executor: ToolExecutor):
        """list_tools should return all discovered tools."""
        tools = executor.list_tools()

        assert len(tools) > 0
        # Should include common tools
        tool_names = {t.name for t in tools}
        assert "list_locations" in tool_names
        assert "list_items" in tool_names

    def test_list_tools_with_permission_filter(self, executor: ToolExecutor):
        """list_tools should filter by permission."""
        read_tools = executor.list_tools(permission_filter=ToolPermission.READ)
        write_tools = executor.list_tools(permission_filter=ToolPermission.WRITE)

        # All read tools should have READ permission
        for tool in read_tools:
            assert tool.permission == ToolPermission.READ

        # All write tools should have WRITE permission
        for tool in write_tools:
            assert tool.permission == ToolPermission.WRITE

        # There should be no overlap
        read_names = {t.name for t in read_tools}
        write_names = {t.name for t in write_tools}
        assert len(read_names & write_names) == 0

    def test_get_tool_schemas_returns_valid_format(self, executor: ToolExecutor):
        """get_tool_schemas should return OpenAI-compatible format."""
        schemas = executor.get_tool_schemas()

        assert len(schemas) > 0
        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]

    def test_get_tool_schemas_filter_to_read_only(self, executor: ToolExecutor):
        """get_tool_schemas with include_write=False should only include READ tools."""
        all_schemas = executor.get_tool_schemas(include_write=True)
        read_schemas = executor.get_tool_schemas(include_write=False)

        # Read-only should be a subset
        assert len(read_schemas) <= len(all_schemas)

        # Verify all returned schemas are for READ tools
        read_schema_names = {s["function"]["name"] for s in read_schemas}
        for name in read_schema_names:
            tool = executor.get_tool(name)
            assert tool is not None
            assert tool.permission == ToolPermission.READ

    def test_requires_approval_for_write_tools(self, executor: ToolExecutor):
        """requires_approval should return True for WRITE and DESTRUCTIVE tools."""
        # create_item is a WRITE tool
        assert executor.requires_approval("create_item") is True

        # delete_item is DESTRUCTIVE
        assert executor.requires_approval("delete_item") is True

        # list_locations is READ
        assert executor.requires_approval("list_locations") is False

    def test_requires_approval_returns_true_for_unknown(self, executor: ToolExecutor):
        """requires_approval should return True for unknown tools (fail-safe)."""
        # Unknown tools return True as a safety measure - if an unknown tool
        # somehow reaches execution, requiring approval adds a safety layer.
        assert executor.requires_approval("nonexistent") is True

    def test_get_permission_returns_correct_permission(self, executor: ToolExecutor):
        """get_permission should return the correct permission level."""
        assert executor.get_permission("list_locations") == ToolPermission.READ
        assert executor.get_permission("create_item") == ToolPermission.WRITE
        assert executor.get_permission("delete_item") == ToolPermission.DESTRUCTIVE

    def test_get_permission_returns_none_for_unknown(self, executor: ToolExecutor):
        """get_permission should return None for unknown tools."""
        assert executor.get_permission("nonexistent") is None

    @pytest.mark.asyncio
    async def test_execute_read_tool_success(
        self, executor: ToolExecutor, mock_client: MagicMock
    ):
        """execute should successfully execute a READ tool."""
        result = await executor.execute("list_locations", {}, "test-token")

        assert result.success is True
        assert result.data is not None
        mock_client.list_locations.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_returns_error(self, executor: ToolExecutor):
        """execute should return error for unknown tool."""
        result = await executor.execute("nonexistent", {}, "test-token")

        assert result.success is False
        assert result.error is not None
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_invalid_params_returns_error(
        self, executor: ToolExecutor
    ):
        """execute should return error for invalid parameters."""
        # get_item requires item_id
        result = await executor.execute("get_item", {}, "test-token")

        assert result.success is False
        assert result.error is not None
        assert "Invalid parameters" in result.error or "validation" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_if_allowed_executes_read_tools(
        self, executor: ToolExecutor, mock_client: MagicMock
    ):
        """execute_if_allowed should execute READ tools."""
        result = await executor.execute_if_allowed(
            "list_locations", {}, "test-token", allow_write=False
        )

        assert result is not None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_if_allowed_skips_write_tools(self, executor: ToolExecutor):
        """execute_if_allowed should return None for WRITE tools when not allowed."""
        result = await executor.execute_if_allowed(
            "create_item", {"name": "Test", "location_id": "loc1"}, "test-token",
            allow_write=False
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_if_allowed_executes_write_when_allowed(
        self, executor: ToolExecutor, mock_client: MagicMock
    ):
        """execute_if_allowed should execute WRITE tools when allow_write=True."""
        mock_client.create_item = AsyncMock(
            return_value={"id": "new-item", "name": "Test"}
        )

        result = await executor.execute_if_allowed(
            "create_item",
            {"name": "Test", "location_id": "loc1"},
            "test-token",
            allow_write=True,
        )

        assert result is not None
        # Note: The result might fail validation, but that's okay for this test
        # The point is that it attempted to execute rather than returning None


class TestToolExecutorCaching:
    """Tests for ToolExecutor caching behavior."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock HomeboxClient."""
        return MagicMock()

    def test_tools_are_discovered_once(self, mock_client: MagicMock):
        """Tools should be discovered only once per executor instance."""
        executor = ToolExecutor(mock_client)

        # Access tools twice
        tools1 = executor.list_tools()
        tools2 = executor.list_tools()

        # Should be the same list (cached)
        assert tools1 == tools2

    def test_schema_cache_is_used(self, mock_client: MagicMock):
        """Tool schemas should be cached."""
        executor = ToolExecutor(mock_client)

        # Access schemas twice
        schemas1 = executor.get_tool_schemas()
        schemas2 = executor.get_tool_schemas()

        # Should be the same list (cached)
        assert schemas1 == schemas2

