"""Live tests for Homebox label printing via mock printer server.

Verifies the end-to-end label print flow by running a mock HTTP printer
server on the host and configuring Homebox to POST labels to it.

Tests verify:
1. Label preview returns a valid PNG image
2. Print-on-server triggers Homebox to POST the label to the mock printer
3. The mock printer receives a valid PNG file body
4. The ``client.print_label()`` method returns the expected acknowledgment

Architecture:
    [Test] --print_label()--> [Homebox Container]
              |                       |
              |     wget --post-file  |
              |                       v
              |             [Mock Printer Server]
              |                       |
              +--- asserts on --------+
                   mock_label_printer.requests
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio

# Import the shared live-test auth and mock printer types for type hints.
from conftest import HomeboxAuth, MockLabelPrinter

from homebox_companion import HomeboxClient
from homebox_companion.homebox import ItemCreate

# All tests in this module require Docker
pytestmark = pytest.mark.live


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _test_item(
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
) -> tuple[str, str]:
    """Create a test item and return its item UUID and asset ID."""
    client = homebox_client
    token = homebox_auth.token

    # Get a location for the item
    locations = await client.list_locations(token)
    assert locations, "Demo data should have at least one location"
    location_id = locations[0]["id"]

    # Create test item
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    item = ItemCreate(
        name=f"Label Print Test {timestamp}",
        quantity=1,
        description="Item for label print testing",
        parent_id=location_id,
    )
    created = await client.create_item(token, item)
    item_id = created["id"]
    # This dependency tears down even if the remaining setup fails before returning.
    cleanup_items.append(item_id)

    await client.ensure_asset_ids(token)
    fetched = await client.get_item(token, item_id)
    asset_id = fetched.get("assetId")
    assert asset_id, "Homebox should assign an asset ID to the test item"

    return item_id, asset_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLabelPreview:
    """Verify the label preview endpoint returns a valid PNG."""

    @pytest.mark.asyncio
    async def test_label_preview_returns_png_image(
        self,
        homebox_client: HomeboxClient,
        homebox_auth: HomeboxAuth,
        _test_item: tuple[str, str],
    ) -> None:
        """GET /labelmaker/asset/{id} without ?print should return a PNG image."""
        _, asset_id = _test_item
        token = homebox_auth.token

        resp = await homebox_client.client.get(
            f"{homebox_client.base_url}/labelmaker/asset/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        content_type = resp.headers.get("content-type", "")
        assert "image/png" in content_type, f"Expected image/png, got {content_type}"
        assert resp.content[:4] == b"\x89PNG", "Response is not a valid PNG file"
        assert len(resp.content) > 100, f"PNG too small ({len(resp.content)} bytes)"


class TestMockPrinterReceivesLabel:
    """Verify that Homebox actually sends the label to the mock printer server."""

    @pytest.mark.asyncio
    async def test_print_triggers_post_to_mock_printer(
        self,
        homebox_client: HomeboxClient,
        homebox_auth: HomeboxAuth,
        homebox_container_name: str,
        mock_label_printer: MockLabelPrinter,
        _test_item: tuple[str, str],
    ) -> None:
        """When print_label is called, Homebox should POST the label PNG
        to the mock printer server."""
        _, asset_id = _test_item
        mock_label_printer.clear()
        result = await homebox_client.print_label(homebox_auth.token, asset_id)

        # Homebox should have returned "Printed!"
        assert "Printed" in result, f"Expected 'Printed' in response, got: {result!r}"

        # The mock printer should have received at least one POST
        assert len(mock_label_printer.requests) >= 1, (
            f"Mock printer received {len(mock_label_printer.requests)} requests, expected >= 1. "
            f"Homebox may not have been able to reach host.docker.internal. "
            f"Check container logs: docker logs {homebox_container_name}"
        )
        delivered = mock_label_printer.requests[-1]
        assert delivered.method == "POST"
        assert delivered.path == "/print"
        assert delivered.body[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(delivered.body) > 100, "Printed label must contain image data"
