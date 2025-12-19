"""Integration tests for HomeboxClient with real demo server.

These tests communicate with the live Homebox demo server at
https://demo.homebox.software and should always be able to run.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from homebox_companion import AuthenticationError, HomeboxClient, ItemCreate


@pytest.mark.asyncio
async def test_login_with_valid_credentials_returns_token(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """Login with valid credentials should return a login response dict."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)

        # Should return a dict with token and expiresAt
        assert response
        assert isinstance(response, dict)
        assert "token" in response
        assert "expiresAt" in response

        # Token should be a non-empty string
        token = response["token"]
        assert isinstance(token, str)
        assert len(token) > 20  # Tokens are typically long strings


@pytest.mark.asyncio
async def test_login_with_invalid_credentials_raises_error(
    homebox_api_url: str,
) -> None:
    """Login with invalid credentials should raise an error."""
    async with HomeboxClient(base_url=homebox_api_url) as client:
        # Demo server returns 500 for invalid credentials, not 401
        with pytest.raises((AuthenticationError, RuntimeError)):
            await client.login("invalid@example.com", "wrongpassword")


@pytest.mark.asyncio
async def test_list_locations_returns_non_empty_list(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """List locations should return a non-empty list with expected structure."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        locations = await client.list_locations(token)

        assert locations
        assert isinstance(locations, list)
        assert len(locations) > 0

        # Check structure of first location
        first_location = locations[0]
        assert "id" in first_location
        assert "name" in first_location
        assert isinstance(first_location["id"], str)
        assert isinstance(first_location["name"], str)


@pytest.mark.asyncio
async def test_list_locations_with_filter_children(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """List locations with filter_children should only return top-level locations."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]

        all_locations = await client.list_locations(token)
        filtered_locations = await client.list_locations(token, filter_children=True)

        # Filtered list should be <= all locations
        assert len(filtered_locations) <= len(all_locations)
        # All filtered locations should have expected structure
        for location in filtered_locations:
            assert "id" in location
            assert "name" in location


@pytest.mark.asyncio
async def test_get_single_location_returns_with_children(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """Get single location should return location with children field."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        locations = await client.list_locations(token)

        assert locations
        location_id = locations[0]["id"]

        location = await client.get_location(token, location_id)

        assert location["id"] == location_id
        assert "name" in location
        assert "children" in location  # Should include children


@pytest.mark.asyncio
async def test_create_item_returns_item_with_id(
    homebox_api_url: str, homebox_credentials: tuple[str, str], cleanup_items: list[str]
) -> None:
    """Create item should return item with ID matching request data."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        locations = await client.list_locations(token)

        assert locations
        location_id = locations[0]["id"]

        # Create unique item name with timestamp
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        item_name = f"Test Item {timestamp}"

        item = ItemCreate(
            name=item_name,
            quantity=3,
            description="Integration test item",
            location_id=location_id,
        )

        created = await client.create_item(token, item)
        cleanup_items.append(created["id"])  # Track for cleanup

        # Verify response structure
        assert "id" in created
        assert created["id"]  # Non-empty ID
        assert created["name"] == item_name
        assert created["quantity"] == 3
        assert created["description"] == "Integration test item"


@pytest.mark.asyncio
async def test_update_item_returns_updated_values(
    homebox_api_url: str, homebox_credentials: tuple[str, str], cleanup_items: list[str]
) -> None:
    """Update item should return item reflecting changes."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        locations = await client.list_locations(token)

        assert locations
        location_id = locations[0]["id"]

        # Create item first
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        item = ItemCreate(
            name=f"Original Name {timestamp}",
            quantity=1,
            description="Original description",
            location_id=location_id,
        )
        created = await client.create_item(token, item)
        item_id = created["id"]
        cleanup_items.append(item_id)  # Track for cleanup

        # Fetch the item to get its full structure
        await client.get_item(token, item_id)

        # Update the item with complete payload
        updated_name = f"Updated Name {timestamp}"
        update_data = {
            "id": item_id,
            "name": updated_name,
            "quantity": 5,
            "description": "Updated description",
            "locationId": location_id,
        }

        updated = await client.update_item(token, item_id, update_data)

        # Verify updates
        assert updated["id"] == item_id
        assert updated["name"] == updated_name
        assert updated["quantity"] == 5
        assert updated["description"] == "Updated description"


@pytest.mark.asyncio
async def test_get_item_returns_full_details(
    homebox_api_url: str, homebox_credentials: tuple[str, str], cleanup_items: list[str]
) -> None:
    """Get item should return full item details."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        locations = await client.list_locations(token)

        assert locations
        location_id = locations[0]["id"]

        # Create item
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        item = ItemCreate(
            name=f"Get Test {timestamp}",
            quantity=2,
            location_id=location_id,
        )
        created = await client.create_item(token, item)
        item_id = created["id"]
        cleanup_items.append(item_id)  # Track for cleanup

        # Get the item
        fetched = await client.get_item(token, item_id)

        assert fetched["id"] == item_id
        assert "name" in fetched
        assert "quantity" in fetched
        assert "location" in fetched  # Full location object


@pytest.mark.asyncio
async def test_list_labels_returns_labels_list(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """List labels should return available labels."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        labels = await client.list_labels(token)

        # Demo server might or might not have labels
        assert isinstance(labels, list)

        # If labels exist, check structure
        if labels:
            first_label = labels[0]
            assert "id" in first_label
            assert "name" in first_label


@pytest.mark.asyncio
async def test_create_location_returns_created_location(
    homebox_api_url: str, homebox_credentials: tuple[str, str], cleanup_locations: list[str]
) -> None:
    """Create location should return the created location."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]

        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        location_name = f"Test Location {timestamp}"

        created = await client.create_location(
            token=token,
            name=location_name,
            description="Integration test location",
        )
        cleanup_locations.append(created["id"])  # Track for cleanup

        assert "id" in created
        assert created["name"] == location_name
        assert created["description"] == "Integration test location"


@pytest.mark.asyncio
async def test_typed_methods_return_correct_types(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """Typed methods should return proper model instances."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]

        # Test list_locations_typed
        locations = await client.list_locations_typed(token)
        assert locations
        # Check it has Location attributes
        assert hasattr(locations[0], "id")
        assert hasattr(locations[0], "name")

        # Test list_labels_typed
        labels = await client.list_labels_typed(token)
        assert isinstance(labels, list)


@pytest.mark.asyncio
async def test_client_context_manager_closes_properly(homebox_api_url: str) -> None:
    """Client should properly close when used as context manager."""
    # This test verifies no exceptions are raised during cleanup
    async with HomeboxClient(base_url=homebox_api_url) as client:
        # Just verify we can use it
        assert client.base_url

    # After context exit, client should be closed
    # (no direct way to test this, but it shouldn't raise errors)


@pytest.mark.asyncio
async def test_delete_item_removes_item(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """Delete item should remove the item from Homebox."""
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        locations = await client.list_locations(token)

        assert locations
        location_id = locations[0]["id"]

        # Create an item
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        item_name = f"Delete Test Item {timestamp}"

        item = ItemCreate(
            name=item_name,
            quantity=1,
            description="Item to be deleted",
            location_id=location_id,
        )

        created = await client.create_item(token, item)
        item_id = created["id"]

        # Verify item exists
        fetched = await client.get_item(token, item_id)
        assert fetched["id"] == item_id

        # Delete the item
        await client.delete_item(token, item_id)

        # Verify item is gone (should raise 404)
        with pytest.raises(RuntimeError) as exc_info:
            await client.get_item(token, item_id)

        # Check it's a 404 error
        assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_nonexistent_item_is_idempotent(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """Delete non-existent item should succeed (idempotent delete).

    Homebox returns 204 for deleting items that don't exist,
    which is correct REST API behavior for idempotent DELETE.
    """
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]

        # Try to delete a non-existent item - should not raise
        fake_id = "00000000-0000-0000-0000-000000000000"
        await client.delete_item(token, fake_id)  # Should not raise


@pytest.mark.asyncio
async def test_create_and_delete_item_cleanup_workflow(
    homebox_api_url: str, homebox_credentials: tuple[str, str]
) -> None:
    """Test the create-then-delete workflow for failed upload cleanup.

    This simulates what happens when an item is created but image upload fails:
    1. Create item
    2. (Image upload would fail here)
    3. Delete item to clean up
    """
    username, password = homebox_credentials

    async with HomeboxClient(base_url=homebox_api_url) as client:
        response = await client.login(username, password)
        token = response["token"]
        locations = await client.list_locations(token)

        assert locations
        location_id = locations[0]["id"]

        # Create item
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        item = ItemCreate(
            name=f"Cleanup Test {timestamp}",
            quantity=1,
            location_id=location_id,
        )
        created = await client.create_item(token, item)
        item_id = created["id"]

        # Simulate upload failure by immediately deleting
        # (In real scenario, this happens after upload retries fail)
        await client.delete_item(token, item_id)

        # Confirm deletion
        with pytest.raises(RuntimeError):
            await client.get_item(token, item_id)
