"""Offline unit tests for Homebox label printing."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from homebox_companion import HomeboxAuthError, HomeboxClient, HomeboxCompanionError
from homebox_companion.core import HomeboxAPIError
from homebox_companion.homebox.models import Item
from server.app import create_app

pytestmark = pytest.mark.unit

ASSET_ID = "000-042"
ENTITY_ID = "entity-uuid-123"
TOKEN = "token-123"
TENANT_ID = "group-456"


@pytest.mark.asyncio
async def test_print_label_uses_asset_endpoint_query_and_scoped_headers() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text="Printed!", headers={"content-type": "text/plain"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HomeboxClient(
            base_url="https://homebox.test/api/v1",
            client=http_client,
            extra_headers_factory=lambda: {"X-Tenant": TENANT_ID},
        )
        result = await client.print_label(TOKEN, ASSET_ID)

    assert result == "Printed!"
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.path == "/api/v1/labelmaker/asset/000-042"
    assert dict(request.url.params) == {"print": "true"}
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert request.headers["accept"] == "text/plain"
    assert request.headers["x-tenant"] == TENANT_ID


@pytest.mark.asyncio
async def test_print_label_preserves_upstream_http_errors() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="asset not found")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = HomeboxClient(base_url="https://homebox.test/api/v1", client=http_client)
        with pytest.raises(HomeboxAPIError, match="404"):
            await client.print_label(TOKEN, ASSET_ID)


def test_item_asset_id_alias_and_missing_default() -> None:
    with_asset = Item.model_validate({"id": ENTITY_ID, "name": "Widget", "assetId": ASSET_ID})
    without_asset = Item.model_validate({"id": ENTITY_ID, "name": "Widget"})

    assert with_asset.asset_id == ASSET_ID
    assert without_asset.asset_id is None


class _RouteClient:
    def __init__(self, item: Item, print_error: Exception | None = None) -> None:
        self.item = item
        self.print_error = print_error
        self.fetched: list[tuple[str, str]] = []
        self.printed: list[tuple[str, str]] = []

    async def get_item_typed(self, token: str, item_id: str) -> Item:
        self.fetched.append((token, item_id))
        return self.item

    async def print_label(self, token: str, asset_id: str) -> str:
        if self.print_error is not None:
            raise self.print_error
        self.printed.append((token, asset_id))
        return "Printed!"


def _route_app(route_client: _RouteClient) -> FastAPI:
    from server.api import items as items_module
    from server.dependencies import get_client, get_token

    app = FastAPI()
    production_app = create_app()
    app.exception_handlers[HomeboxCompanionError] = production_app.exception_handlers[HomeboxCompanionError]
    app.include_router(items_module.router)
    app.dependency_overrides[get_client] = lambda: route_client
    app.dependency_overrides[get_token] = lambda: TOKEN
    return app


def test_print_route_resolves_entity_uuid_to_asset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.api import items as items_module

    monkeypatch.setattr(items_module.settings, "print_enabled", True)
    route_client = _RouteClient(Item.model_validate({"id": ENTITY_ID, "name": "Widget", "assetId": ASSET_ID}))

    with TestClient(_route_app(route_client)) as client:
        response = client.post(f"/items/{ENTITY_ID}/print-label")

    assert response.status_code == 200
    assert response.json() == {"message": "Printed!"}
    assert route_client.fetched == [(TOKEN, ENTITY_ID)]
    assert route_client.printed == [(TOKEN, ASSET_ID)]


def test_print_route_returns_409_when_asset_id_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.api import items as items_module

    monkeypatch.setattr(items_module.settings, "print_enabled", True)
    route_client = _RouteClient(Item.model_validate({"id": ENTITY_ID, "name": "Widget"}))

    with TestClient(_route_app(route_client)) as client:
        response = client.post(f"/items/{ENTITY_ID}/print-label")

    assert response.status_code == 409
    assert response.json() == {"detail": "Item does not have an asset ID assigned yet."}
    assert route_client.fetched == [(TOKEN, ENTITY_ID)]
    assert route_client.printed == []


def test_print_route_returns_403_when_printing_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.api import items as items_module

    monkeypatch.setattr(items_module.settings, "print_enabled", False)
    route_client = _RouteClient(Item.model_validate({"id": ENTITY_ID, "name": "Widget"}))

    with TestClient(_route_app(route_client)) as client:
        response = client.post(f"/items/{ENTITY_ID}/print-label")

    assert response.status_code == 403
    assert response.json() == {"detail": "Label printing is not enabled on this server (HBC_PRINT_ENABLED=false)."}
    assert route_client.fetched == []
    assert route_client.printed == []


@pytest.mark.parametrize(
    ("error", "status_code", "error_code", "detail"),
    [
        (
            HomeboxAuthError("expired token", user_message="Authentication failed"),
            401,
            "AUTH_FAILED",
            "Authentication failed",
        ),
        (
            HomeboxAPIError("printer unavailable", user_message="Homebox could not print the label"),
            502,
            "HOMEBOX_ERROR",
            "Homebox could not print the label",
        ),
    ],
)
def test_print_route_preserves_structured_domain_errors(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    error_code: str,
    detail: str,
) -> None:
    from server.api import items as items_module

    monkeypatch.setattr(items_module.settings, "print_enabled", True)
    route_client = _RouteClient(
        Item.model_validate({"id": ENTITY_ID, "name": "Widget", "assetId": ASSET_ID}),
        print_error=error,
    )

    with TestClient(_route_app(route_client)) as client:
        response = client.post(f"/items/{ENTITY_ID}/print-label")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail, "code": error_code}


def test_print_route_wraps_unexpected_errors_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from server.api import items as items_module

    monkeypatch.setattr(items_module.settings, "print_enabled", True)
    route_client = _RouteClient(
        Item.model_validate({"id": ENTITY_ID, "name": "Widget", "assetId": ASSET_ID}),
        print_error=RuntimeError("private upstream failure detail"),
    )

    with TestClient(_route_app(route_client)) as client:
        response = client.post(f"/items/{ENTITY_ID}/print-label")

    assert response.status_code == 502
    assert response.json() == {
        "detail": ("Failed to print label. Ensure HBOX_LABEL_MAKER_PRINT_COMMAND is configured on the Homebox server."),
        "code": "HOMEBOX_ERROR",
    }
    assert "private upstream failure detail" not in response.text
