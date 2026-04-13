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

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio

# Import the MockLabelPrinter type for type hints
from conftest import MockLabelPrinter

from homebox_companion import HomeboxClient
from homebox_companion.homebox import ItemCreate

# All tests in this module require Docker
pytestmark = pytest.mark.live


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def _test_item(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> AsyncGenerator[str]:
    """Create a test item and return its ID. Cleaned up after module."""
    username, password = homebox_credentials
    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]

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
            location_id=location_id,
        )
        created = await client.create_item(token, item)
        item_id = created["id"]

        yield item_id

        # Cleanup
        try:
            await client.delete_item(token, item_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLabelPreview:
    """Verify the label preview endpoint returns a valid PNG."""

    @pytest.mark.asyncio
    async def test_label_preview_returns_png_image(
        self,
        homebox_api_url: str,
        homebox_credentials: tuple[str, str],
        _test_item: str,
    ) -> None:
        """GET /labelmaker/item/{id} without ?print should return a PNG image."""
        username, password = homebox_credentials
        item_id = _test_item

        async with HomeboxClient(base_url=homebox_api_url) as client:
            response = await client.login(username, password)
            token = response["token"]

            resp = await client.client.get(
                f"{client.base_url}/labelmaker/item/{item_id}",
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
        homebox_api_url: str,
        homebox_credentials: tuple[str, str],
        homebox_container_name: str,
        mock_label_printer: MockLabelPrinter,
        _test_item: str,
    ) -> None:
        """When print_label is called, Homebox should POST the label PNG
        to the mock printer server."""
        username, password = homebox_credentials
        item_id = _test_item
        mock_label_printer.clear()

        async with HomeboxClient(base_url=homebox_api_url) as client:
            response = await client.login(username, password)
            token = response["token"]

            result = await client.print_label(token, item_id)

        # Homebox should have returned "Printed!"
        assert "Printed" in result, f"Expected 'Printed' in response, got: {result!r}"

        # The mock printer should have received at least one POST
        assert len(mock_label_printer.requests) >= 1, (
            f"Mock printer received {len(mock_label_printer.requests)} requests, expected >= 1. "
            f"Homebox may not have been able to reach host.docker.internal. "
            f"Check container logs: docker logs {homebox_container_name}"
        )

    @pytest.mark.asyncio
    async def test_mock_printer_receives_valid_png(
        self,
        homebox_api_url: str,
        homebox_credentials: tuple[str, str],
        mock_label_printer: MockLabelPrinter,
        _test_item: str,
    ) -> None:
        """The POST body sent to the mock printer should be a valid PNG image."""
        username, password = homebox_credentials
        item_id = _test_item
        mock_label_printer.clear()

        async with HomeboxClient(base_url=homebox_api_url) as client:
            response = await client.login(username, password)
            token = response["token"]
            await client.print_label(token, item_id)

        assert mock_label_printer.requests, "No requests received by mock printer"
        last_request = mock_label_printer.requests[-1]

        # Verify the body is a valid PNG (starts with PNG magic bytes)
        assert last_request.body[:4] == b"\x89PNG", (
            f"Expected PNG magic bytes, got: {last_request.body[:4]!r}"
        )
        # A real label image should be at least a few hundred bytes
        assert len(last_request.body) > 100, (
            f"PNG body too small ({len(last_request.body)} bytes), probably not a real label"
        )

    @pytest.mark.asyncio
    async def test_mock_printer_receives_post_to_correct_path(
        self,
        homebox_api_url: str,
        homebox_credentials: tuple[str, str],
        mock_label_printer: MockLabelPrinter,
        _test_item: str,
    ) -> None:
        """The POST should hit the /print path on the mock printer."""
        username, password = homebox_credentials
        item_id = _test_item
        mock_label_printer.clear()

        async with HomeboxClient(base_url=homebox_api_url) as client:
            response = await client.login(username, password)
            token = response["token"]
            await client.print_label(token, item_id)

        assert mock_label_printer.requests, "No requests received by mock printer"
        last_request = mock_label_printer.requests[-1]

        assert last_request.method == "POST"
        assert last_request.path == "/print", (
            f"Expected POST to /print, got {last_request.path}"
        )
