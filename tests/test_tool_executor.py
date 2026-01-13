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
        client.list_locations = AsyncMock(return_value=[{"id": "loc1", "name": "Test Location"}])
        client.list_items = AsyncMock(return_value=[])
        client.list_labels = AsyncMock(return_value=[])
        client.get_item = AsyncMock(return_value={"id": "item1", "name": "Test Item"})
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

    @pytest.mark.asyncio
    async def test_execute_read_tool_success(self, executor: ToolExecutor, mock_client: MagicMock):
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
    async def test_execute_with_invalid_params_returns_error(self, executor: ToolExecutor):
        """execute should return error for invalid parameters."""
        # get_item requires item_id
        result = await executor.execute("get_item", {}, "test-token")

        assert result.success is False
        assert result.error is not None
        assert "Invalid parameters" in result.error or "validation" in result.error.lower()


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


class TestGetDisplayInfo:
    """Tests for ToolExecutor.get_display_info method."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock HomeboxClient with all required methods."""
        client = MagicMock()
        client.get_item = AsyncMock(return_value={"id": "item1", "name": "Test Item", "assetId": "000-001"})
        client.get_location = AsyncMock(return_value={"id": "loc1", "name": "Living Room"})
        client.get_label = AsyncMock(return_value={"id": "label1", "name": "Electronics"})
        return client

    @pytest.fixture
    def executor(self, mock_client: MagicMock) -> ToolExecutor:
        """Create a ToolExecutor with mocked client."""
        return ToolExecutor(mock_client)

    @pytest.mark.asyncio
    async def test_get_display_info_for_update_item(self, executor: ToolExecutor, mock_client: MagicMock):
        """get_display_info should fetch item name for update_item."""
        info = await executor.get_display_info("update_item", {"item_id": "item1"}, "test-token")

        assert info.action_type == "update"
        assert info.target_name == "Test Item"
        assert info.item_name == "Test Item"
        mock_client.get_item.assert_awaited_once_with("test-token", "item1")

    @pytest.mark.asyncio
    async def test_get_display_info_for_delete_item(self, executor: ToolExecutor, mock_client: MagicMock):
        """get_display_info should fetch item name for delete_item."""
        mock_client.get_item.return_value = {
            "id": "item1",
            "name": "Test Item",
            "location": {"name": "Kitchen"},
        }
        info = await executor.get_display_info("delete_item", {"item_id": "item1"}, "test-token")

        assert info.action_type == "delete"
        assert info.target_name == "Test Item"
        assert info.location == "Kitchen"

    @pytest.mark.asyncio
    async def test_get_display_info_for_create_item(self, executor: ToolExecutor):
        """get_display_info should use params name for create_item."""
        info = await executor.get_display_info("create_item", {"name": "New Item", "location_id": "loc1"}, "test-token")

        assert info.action_type == "create"
        assert info.target_name == "New Item"
        assert info.item_name == "New Item"

    @pytest.mark.asyncio
    async def test_get_display_info_for_update_location(self, executor: ToolExecutor, mock_client: MagicMock):
        """get_display_info should fetch location name for update_location."""
        info = await executor.get_display_info("update_location", {"location_id": "loc1"}, "test-token")

        assert info.action_type == "update"
        assert info.target_name == "Living Room"
        mock_client.get_location.assert_awaited_once_with("test-token", "loc1")

    @pytest.mark.asyncio
    async def test_get_display_info_for_delete_location(self, executor: ToolExecutor, mock_client: MagicMock):
        """get_display_info should fetch location name for delete_location."""
        info = await executor.get_display_info("delete_location", {"location_id": "loc1"}, "test-token")

        assert info.action_type == "delete"
        assert info.target_name == "Living Room"

    @pytest.mark.asyncio
    async def test_get_display_info_for_create_location(self, executor: ToolExecutor):
        """get_display_info should use params name for create_location."""
        info = await executor.get_display_info("create_location", {"name": "Garage"}, "test-token")

        assert info.action_type == "create"
        assert info.target_name == "Garage"

    @pytest.mark.asyncio
    async def test_get_display_info_for_update_label(self, executor: ToolExecutor, mock_client: MagicMock):
        """get_display_info should fetch label name for update_label."""
        info = await executor.get_display_info("update_label", {"label_id": "label1"}, "test-token")

        assert info.action_type == "update"
        assert info.target_name == "Electronics"
        mock_client.get_label.assert_awaited_once_with("test-token", "label1")

    @pytest.mark.asyncio
    async def test_get_display_info_for_delete_label(self, executor: ToolExecutor, mock_client: MagicMock):
        """get_display_info should fetch label name for delete_label."""
        info = await executor.get_display_info("delete_label", {"label_id": "label1"}, "test-token")

        assert info.action_type == "delete"
        assert info.target_name == "Electronics"

    @pytest.mark.asyncio
    async def test_get_display_info_for_create_label(self, executor: ToolExecutor):
        """get_display_info should use params name for create_label."""
        info = await executor.get_display_info("create_label", {"name": "Fragile"}, "test-token")

        assert info.action_type == "create"
        assert info.target_name == "Fragile"

    @pytest.mark.asyncio
    async def test_get_display_info_handles_api_error_gracefully(self, executor: ToolExecutor, mock_client: MagicMock):
        """get_display_info should return defaults on API error."""
        mock_client.get_location.side_effect = Exception("API error")

        info = await executor.get_display_info("update_location", {"location_id": "loc1"}, "test-token")

        # Should return DisplayInfo with action_type but no target_name
        assert info.action_type == "update"
        assert info.target_name is None
