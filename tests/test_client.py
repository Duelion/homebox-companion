from __future__ import annotations

import json as jsonlib
from typing import Any

import httpx

from homebox_vision import HomeboxClient


class MockTransport(httpx.BaseTransport):
    """Mock transport for testing HTTPX client."""

    def __init__(
        self,
        *,
        get_json: Any = None,
        put_json: Any = None,
        put_status: int = 200,
    ) -> None:
        self.get_json = get_json
        self.put_json = put_json
        self.put_status = put_status
        self.calls: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(
            {
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "params": dict(request.url.params) if request.url.params else None,
                "json": jsonlib.loads(request.content) if request.content else None,
            }
        )

        if request.method == "GET":
            return httpx.Response(
                status_code=200,
                json=self.get_json or [],
            )
        elif request.method == "PUT":
            return httpx.Response(
                status_code=self.put_status,
                json=self.put_json or {},
            )
        else:
            return httpx.Response(status_code=200, json={})


def test_list_locations_supports_filter_children_flag() -> None:
    transport = MockTransport(
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
    http_client = httpx.Client(transport=transport)
    client = HomeboxClient(client=http_client)

    locations = client.list_locations("token", filter_children=True)

    assert locations[0]["id"] == "loc-1"
    call = transport.calls[0]
    assert "/locations" in call["url"]
    assert call["headers"]["authorization"] == "Bearer token"
    assert call["headers"]["accept"] == "application/json"
    assert call["params"] == {"filterChildren": "true"}


def test_list_locations_omits_filter_children_when_not_requested() -> None:
    transport = MockTransport(get_json=[])
    http_client = httpx.Client(transport=transport)
    client = HomeboxClient(client=http_client)

    client.list_locations("token")

    call = transport.calls[0]
    assert call["params"] is None or call["params"] == {}


def test_update_item_sends_payload_and_returns_response() -> None:
    transport = MockTransport(put_json={"id": "item-1", "name": "Updated"})
    http_client = httpx.Client(transport=transport)
    client = HomeboxClient(client=http_client)

    payload = {"name": "Updated", "quantity": 2}
    response = client.update_item("token", "item-1", payload)

    call = transport.calls[0]
    assert "/items/item-1" in call["url"]
    assert call["json"] == payload
    assert call["headers"]["authorization"] == "Bearer token"
    assert call["headers"]["content-type"] == "application/json"
    assert response == {"id": "item-1", "name": "Updated"}
