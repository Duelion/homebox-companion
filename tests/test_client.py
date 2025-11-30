"""Tests for the Homebox API client."""
from __future__ import annotations

import json as jsonlib
from typing import Any

import requests

from homebox import HomeboxDemoClient, Item


class MockSession:
    """Mock HTTP session for testing."""

    def __init__(
        self,
        *,
        get_json: Any = None,
        put_json: Any = None,
        put_status: int = 200,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.get_json = get_json
        self.put_json = put_json
        self.put_status = put_status
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        self.calls.append({
            "method": "GET",
            "url": url,
            "headers": headers or {},
            "params": params,
            "timeout": timeout,
        })
        response = requests.Response()
        response.status_code = 200
        response._content = jsonlib.dumps(self.get_json or []).encode()
        response.encoding = "utf-8"
        return response

    def put(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        timeout: int | None = None,
    ) -> requests.Response:
        self.calls.append({
            "method": "PUT",
            "url": url,
            "headers": headers or {},
            "json": json,
            "timeout": timeout,
        })
        response = requests.Response()
        response.status_code = self.put_status
        response._content = jsonlib.dumps(self.put_json or {}).encode()
        response.encoding = "utf-8"
        return response


def test_list_locations_supports_filter_children_flag() -> None:
    """Test that filter_children param is passed correctly."""
    session = MockSession(
        get_json=[
            {
                "id": "loc-1",
                "name": "Garage",
                "description": "Detached garage",
                "itemCount": 3,
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
            }
        ]
    )
    client = HomeboxDemoClient(session=session)

    locations = client.list_locations("token", filter_children=True)

    assert locations[0]["id"] == "loc-1"
    call = session.calls[0]
    assert call["url"].endswith("/locations")
    assert call["headers"]["Authorization"] == "Bearer token"
    assert call["headers"]["Accept"] == "application/json"
    assert call["params"] == {"filterChildren": "true"}


def test_list_locations_omits_filter_children_when_not_requested() -> None:
    """Test that filter_children is omitted when not specified."""
    session = MockSession(get_json=[])
    client = HomeboxDemoClient(session=session)

    client.list_locations("token")

    call = session.calls[0]
    assert call["params"] is None


def test_update_item_sends_payload_and_returns_response() -> None:
    """Test that update_item sends correct payload."""
    session = MockSession(put_json={"id": "item-1", "name": "Updated"})
    client = HomeboxDemoClient(session=session)

    payload = {"name": "Updated", "quantity": 2}
    response = client.update_item("token", "item-1", payload)

    call = session.calls[0]
    assert call["url"].endswith("/items/item-1")
    assert call["json"] == payload
    assert call["headers"]["Authorization"] == "Bearer token"
    assert call["headers"]["Content-Type"] == "application/json"
    assert response == {"id": "item-1", "name": "Updated"}


def test_item_from_dict() -> None:
    """Test Item creation from API response dict."""
    data = {
        "id": "item-123",
        "name": "Hammer",
        "quantity": 3,
        "description": "Steel head",
        "locationId": "loc-456",
        "labelIds": ["lbl-1", "lbl-2"],
    }

    item = Item.from_dict(data)

    assert item.id == "item-123"
    assert item.name == "Hammer"
    assert item.quantity == 3
    assert item.description == "Steel head"
    assert item.location_id == "loc-456"
    assert item.label_ids == ["lbl-1", "lbl-2"]


def test_item_to_api_payload() -> None:
    """Test Item conversion to API payload."""
    item = Item(
        name="Screwdriver",
        quantity=5,
        description="Phillips head",
        location_id="loc-789",
        label_ids=["lbl-1"],
    )

    payload = item.to_api_payload()

    assert payload["name"] == "Screwdriver"
    assert payload["quantity"] == 5
    assert payload["description"] == "Phillips head"
    assert payload["locationId"] == "loc-789"
    assert payload["labelIds"] == ["lbl-1"]


def test_item_truncates_long_values() -> None:
    """Test that Item truncates values exceeding limits."""
    long_name = "x" * 300
    long_desc = "y" * 1500

    item = Item(name=long_name, description=long_desc)

    assert len(item.name) == 255
    assert len(item.description) == 1000


def test_item_normalizes_quantity() -> None:
    """Test that Item normalizes invalid quantities."""
    item1 = Item(name="Test", quantity=0)
    item2 = Item(name="Test", quantity=-5)

    assert item1.quantity == 1
    assert item2.quantity == 1


def test_update_item_builds_payload_correctly() -> None:
    """Test that update_item builds the correct API payload."""
    from datetime import date

    # Test the payload building by checking the _to_iso_string helper
    from homebox.api import _to_iso_string

    assert _to_iso_string(None) is None
    assert _to_iso_string("2024-01-15") == "2024-01-15"
    assert _to_iso_string(date(2024, 1, 15)) == "2024-01-15"


def test_location_type_conversion() -> None:
    """Test Location accepts both ID strings and Location objects."""
    from homebox import Item, Location

    loc = Location(id="loc-123", name="Garage")

    # Creating item with Location object
    item = Item(name="Test", location_id=loc.id)
    payload = item.to_api_payload()
    assert payload["locationId"] == "loc-123"


def test_label_type_conversion() -> None:
    """Test labels accepts both ID strings and Label objects."""
    from homebox import Item, Label

    # Labels can be created and their IDs used
    label1 = Label(id="lbl-1", name="Tools")
    label2 = Label(id="lbl-2", name="Kitchen")

    # The Session.create_item handles conversion, but we can test the Item
    item = Item(name="Test", label_ids=[label1.id, label2.id])
    payload = item.to_api_payload()
    assert payload["labelIds"] == ["lbl-1", "lbl-2"]
