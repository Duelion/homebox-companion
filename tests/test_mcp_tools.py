"""Unit tests for MCP tools.

These tests verify the MCP tool implementations using mocked HomeboxClient
responses. For live integration tests with real Homebox, see the live marker tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homebox_companion.mcp.tools import HomeboxMCPTools, ToolPermission, ToolResult

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock HomeboxClient."""
    client = MagicMock()
    # Make all methods async mocks
    client.list_locations = AsyncMock()
    client.get_location = AsyncMock()
    client.list_labels = AsyncMock()
    client.list_items = AsyncMock()
    client.get_item = AsyncMock()
    return client


@pytest.fixture
def tools(mock_client: MagicMock) -> HomeboxMCPTools:
    """Create HomeboxMCPTools instance with mock client."""
    return HomeboxMCPTools(mock_client)


# =============================================================================
# ToolResult Tests
# =============================================================================


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result_to_dict(self):
        """Successful result should include data in dict."""
        result = ToolResult(success=True, data={"id": "123", "name": "Test"})
        assert result.to_dict() == {"success": True, "data": {"id": "123", "name": "Test"}}

    def test_error_result_to_dict(self):
        """Error result should include error message in dict."""
        result = ToolResult(success=False, error="Something went wrong")
        assert result.to_dict() == {"success": False, "error": "Something went wrong"}


# =============================================================================
# Tool Metadata Tests
# =============================================================================


class TestToolMetadata:
    """Tests for tool metadata and permissions."""

    def test_get_tool_metadata_returns_all_tools(self):
        """Metadata should include all defined tools."""
        metadata = HomeboxMCPTools.get_tool_metadata()

        expected_tools = [
            "list_locations", "get_location", "list_labels", "list_items", "get_item",
            "create_item", "update_item", "delete_item"
        ]
        assert all(tool in metadata for tool in expected_tools)

    def test_all_phase_a_tools_are_read_only(self):
        """Phase A tools (list/get) should have READ permission."""
        metadata = HomeboxMCPTools.get_tool_metadata()
        phase_a_tools = ["list_locations", "get_location", "list_labels", "list_items", "get_item"]

        for name in phase_a_tools:
            assert (
                metadata[name]["permission"] == ToolPermission.READ
            ), f"{name} should be READ permission"

    def test_phase_d_write_tools_have_correct_permissions(self):
        """Phase D write tools should have WRITE or DESTRUCTIVE permissions."""
        metadata = HomeboxMCPTools.get_tool_metadata()

        assert metadata["create_item"]["permission"] == ToolPermission.WRITE
        assert metadata["update_item"]["permission"] == ToolPermission.WRITE
        assert metadata["delete_item"]["permission"] == ToolPermission.DESTRUCTIVE

    def test_tool_metadata_has_required_fields(self):
        """Each tool metadata should have description, permission, and parameters."""
        metadata = HomeboxMCPTools.get_tool_metadata()

        for name, meta in metadata.items():
            assert "description" in meta, f"{name} missing description"
            assert "permission" in meta, f"{name} missing permission"
            assert "parameters" in meta, f"{name} missing parameters"
            assert (
                meta["parameters"].get("type") == "object"
            ), f"{name} parameters should be object type"


# =============================================================================
# list_locations Tests
# =============================================================================


class TestListLocations:
    """Tests for list_locations tool."""

    @pytest.mark.asyncio
    async def test_returns_locations_on_success(
        self, tools: HomeboxMCPTools, mock_client: MagicMock
    ):
        """Should return locations list on successful API call."""
        mock_locations = [
            {"id": "loc1", "name": "Living Room"},
            {"id": "loc2", "name": "Kitchen"},
        ]
        mock_client.list_locations.return_value = mock_locations

        result = await tools.list_locations("test-token")

        assert result.success is True
        assert result.data == mock_locations
        mock_client.list_locations.assert_called_once_with("test-token", filter_children=None)

    @pytest.mark.asyncio
    async def test_passes_filter_children_parameter(
        self, tools: HomeboxMCPTools, mock_client: MagicMock
    ):
        """Should pass filter_children to client when True."""
        mock_client.list_locations.return_value = []

        await tools.list_locations("test-token", filter_children=True)

        mock_client.list_locations.assert_called_once_with("test-token", filter_children=True)

    @pytest.mark.asyncio
    async def test_returns_error_on_exception(self, tools: HomeboxMCPTools, mock_client: MagicMock):
        """Should return error result when API call fails."""
        mock_client.list_locations.side_effect = Exception("Connection failed")

        result = await tools.list_locations("test-token")

        assert result.success is False
        assert result.error is not None
        assert "Connection failed" in result.error


# =============================================================================
# get_location Tests
# =============================================================================


class TestGetLocation:
    """Tests for get_location tool."""

    @pytest.mark.asyncio
    async def test_returns_location_on_success(
        self, tools: HomeboxMCPTools, mock_client: MagicMock
    ):
        """Should return location details on successful API call."""
        mock_location = {
            "id": "loc1",
            "name": "Living Room",
            "children": [{"id": "loc1a", "name": "Shelf"}],
        }
        mock_client.get_location.return_value = mock_location

        result = await tools.get_location("test-token", location_id="loc1")

        assert result.success is True
        assert result.data == mock_location
        mock_client.get_location.assert_called_once_with("test-token", "loc1")

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_location(
        self, tools: HomeboxMCPTools, mock_client: MagicMock
    ):
        """Should return error when location not found."""
        mock_client.get_location.side_effect = Exception("Location not found")

        result = await tools.get_location("test-token", location_id="nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()


# =============================================================================
# list_labels Tests
# =============================================================================


class TestListLabels:
    """Tests for list_labels tool."""

    @pytest.mark.asyncio
    async def test_returns_labels_on_success(self, tools: HomeboxMCPTools, mock_client: MagicMock):
        """Should return labels list on successful API call."""
        mock_labels = [
            {"id": "lbl1", "name": "Electronics"},
            {"id": "lbl2", "name": "Furniture"},
        ]
        mock_client.list_labels.return_value = mock_labels

        result = await tools.list_labels("test-token")

        assert result.success is True
        assert result.data == mock_labels
        mock_client.list_labels.assert_called_once_with("test-token")


# =============================================================================
# list_items Tests
# =============================================================================


class TestListItems:
    """Tests for list_items tool."""

    @pytest.mark.asyncio
    async def test_returns_items_on_success(self, tools: HomeboxMCPTools, mock_client: MagicMock):
        """Should return items list on successful API call."""
        mock_items = [
            {"id": "item1", "name": "TV"},
            {"id": "item2", "name": "Couch"},
        ]
        mock_client.list_items.return_value = mock_items

        # Use compact=False to get raw items without transformation
        result = await tools.list_items("test-token", compact=False)

        assert result.success is True
        assert result.data == mock_items
        mock_client.list_items.assert_called_once_with(
            "test-token", location_id=None, label_ids=None, page=None, page_size=50
        )

    @pytest.mark.asyncio
    async def test_filters_by_location(self, tools: HomeboxMCPTools, mock_client: MagicMock):
        """Should pass location_id filter to client."""
        mock_client.list_items.return_value = []

        await tools.list_items("test-token", location_id="loc1")

        mock_client.list_items.assert_called_once_with(
            "test-token", location_id="loc1", label_ids=None, page=None, page_size=50
        )


# =============================================================================
# get_item Tests
# =============================================================================


class TestGetItem:
    """Tests for get_item tool."""

    @pytest.mark.asyncio
    async def test_returns_item_on_success(self, tools: HomeboxMCPTools, mock_client: MagicMock):
        """Should return full item details on successful API call."""
        mock_item = {
            "id": "item1",
            "name": "Smart TV",
            "description": "65 inch OLED",
            "location": {"id": "loc1", "name": "Living Room"},
            "labels": [{"id": "lbl1", "name": "Electronics"}],
        }
        mock_client.get_item.return_value = mock_item

        result = await tools.get_item("test-token", item_id="item1")

        assert result.success is True
        assert result.data == mock_item
        mock_client.get_item.assert_called_once_with("test-token", "item1")

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_item(
        self, tools: HomeboxMCPTools, mock_client: MagicMock
    ):
        """Should return error when item not found."""
        mock_client.get_item.side_effect = Exception("Item not found")

        result = await tools.get_item("test-token", item_id="nonexistent")

        assert result.success is False
        assert "not found" in result.error.lower()


# =============================================================================
# Live Integration Tests (require real Homebox demo server)
# =============================================================================


@pytest.mark.live
class TestMCPToolsLive:
    """Live integration tests for MCP tools against demo server."""

    @pytest.mark.asyncio
    async def test_list_locations_live(
        self, homebox_api_url: str, homebox_credentials: tuple[str, str]
    ):
        """List locations should return data from demo server."""
        from homebox_companion import HomeboxClient

        username, password = homebox_credentials
        async with HomeboxClient(base_url=homebox_api_url) as client:
            response = await client.login(username, password)
            token = response["token"]

            tools = HomeboxMCPTools(client)
            result = await tools.list_locations(token)

            assert result.success is True
            assert isinstance(result.data, list)
            # Demo server should have at least some locations
            assert len(result.data) > 0

    @pytest.mark.asyncio
    async def test_list_labels_live(
        self, homebox_api_url: str, homebox_credentials: tuple[str, str]
    ):
        """List labels should return data from demo server."""
        from homebox_companion import HomeboxClient

        username, password = homebox_credentials
        async with HomeboxClient(base_url=homebox_api_url) as client:
            response = await client.login(username, password)
            token = response["token"]

            tools = HomeboxMCPTools(client)
            result = await tools.list_labels(token)

            assert result.success is True
            assert isinstance(result.data, list)
