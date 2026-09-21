"""Unit tests for token refresh response normalization.

Homebox (sysadminsmedia) >= 0.24 returns the refreshed token from
``GET /users/refresh`` in a field named ``raw`` (``UserAuthTokenDetail``),
unlike login which returns ``token`` (``TokenResponse``). These tests pin
the normalization so a "successful" refresh never yields an empty token.
See issue #160.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from homebox_companion import HomeboxAuthError
from homebox_companion.core.exceptions import HomeboxAPIError
from homebox_companion.homebox.client import HomeboxClient

pytestmark = pytest.mark.unit


ResponseFactory = Callable[[httpx.Request], httpx.Response]


@asynccontextmanager
async def _client_with_response(
    handler: ResponseFactory,
    *,
    extra_headers_factory: Callable[[], dict[str, str]] | None = None,
) -> AsyncIterator[HomeboxClient]:
    """Yield a client while explicitly owning its injected HTTP client."""
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        yield HomeboxClient(
            base_url="http://homebox.test/api/v1",
            client=http_client,
            extra_headers_factory=extra_headers_factory,
        )


@asynccontextmanager
async def _client_returning(payload: Any, status_code: int = 200) -> AsyncIterator[HomeboxClient]:
    """Yield a client returning a JSON payload with the requested status."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    async with _client_with_response(handler) as client:
        yield client


@pytest.mark.asyncio
async def test_refresh_token_normalizes_raw_field_to_token_and_preserves_metadata() -> None:
    """Homebox >=0.24 refresh responses carry the token in ``raw``."""
    async with _client_returning(
        {
            "raw": "new-token-from-homebox",
            "attachmentToken": "att",
            "expiresAt": "2026-08-25T00:00:00Z",
        }
    ) as client:
        data = await client.refresh_token("old-token")

    assert data["token"] == "new-token-from-homebox"
    assert data["raw"] == "new-token-from-homebox"
    assert data["attachmentToken"] == "att"
    assert data["expiresAt"] == "2026-08-25T00:00:00Z"


@pytest.mark.asyncio
async def test_refresh_token_prefers_valid_raw_when_legacy_token_is_empty() -> None:
    async with _client_returning({"token": "", "raw": "Bearer fallback-token"}) as client:
        data = await client.refresh_token("old-token")

    assert data["token"] == "fallback-token"


@pytest.mark.asyncio
async def test_refresh_token_keeps_legacy_token_field_and_strips_bearer() -> None:
    """Legacy refresh responses with a ``token`` field keep working."""
    async with _client_returning(
        {"token": "Bearer legacy-token", "expiresAt": "2026-08-25T00:00:00Z"}
    ) as client:
        data = await client.refresh_token("old-token")

    assert data["token"] == "legacy-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([], id="non-object"),
        pytest.param({}, id="missing-token"),
        pytest.param({"token": None}, id="null-token"),
        pytest.param({"raw": 123}, id="non-string-token"),
        pytest.param({"raw": ""}, id="empty-token"),
        pytest.param({"raw": "Bearer "}, id="bearer-only"),
        pytest.param({"raw": "  token"}, id="leading-whitespace"),
        pytest.param({"raw": "to ken"}, id="internal-whitespace"),
        pytest.param({"raw": "token\n"}, id="trailing-whitespace"),
    ],
)
async def test_refresh_token_rejects_malformed_success_payload(payload: Any) -> None:
    async with _client_returning(payload) as client:
        with pytest.raises(HomeboxAPIError) as caught:
            await client.refresh_token("old-token")

    assert caught.value.user_message == "Homebox returned an invalid token refresh response. Please try again."


@pytest.mark.asyncio
async def test_refresh_token_rejects_invalid_json_success() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", headers={"content-type": "application/json"})

    async with _client_with_response(handler) as client:
        with pytest.raises(HomeboxAPIError) as caught:
            await client.refresh_token("old-token")

    assert caught.value.user_message == "Homebox returned an invalid token refresh response. Please try again."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        pytest.param(401, HomeboxAuthError, id="unauthorized"),
        pytest.param(403, HomeboxAPIError, id="forbidden"),
        pytest.param(500, HomeboxAPIError, id="upstream-error"),
    ],
)
async def test_refresh_token_preserves_upstream_error_classification(
    status_code: int, error_type: type[Exception]
) -> None:
    async with _client_returning({"detail": "upstream"}, status_code=status_code) as client:
        with pytest.raises(error_type):
            await client.refresh_token("old-token")


@pytest.mark.asyncio
async def test_refresh_token_does_not_send_tenant_header() -> None:
    seen_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update({key.lower(): value for key, value in request.headers.items()})
        return httpx.Response(200, json={"raw": "new-token"})

    async with _client_with_response(
        handler, extra_headers_factory=lambda: {"X-Tenant": "should-not-be-sent"}
    ) as client:
        await client.refresh_token("old-token")

    assert seen_headers["authorization"] == "Bearer old-token"
    assert seen_headers["accept"] == "application/json"
    assert "x-tenant" not in seen_headers


@pytest.mark.asyncio
async def test_refresh_route_returns_canonical_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.api import auth as auth_api
    from server.app import create_app

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"raw": "Bearer refreshed-token", "expiresAt": "2026-08-25T00:00:00Z"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream_http:
        homebox_client = HomeboxClient(base_url="http://homebox.test/api/v1", client=upstream_http)
        monkeypatch.setattr(auth_api, "get_client", lambda: homebox_client)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://testserver"
        ) as api_client:
            response = await api_client.post(
                "/api/refresh", headers={"Authorization": "Bearer old-token"}
            )

    assert response.status_code == 200
    assert response.json() == {
        "token": "refreshed-token",
        "expires_at": "2026-08-25T00:00:00Z",
        "message": "Login successful",
    }


@pytest.mark.asyncio
async def test_refresh_route_returns_safe_502_for_malformed_upstream_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from server.api import auth as auth_api
    from server.app import create_app

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream_http:
        homebox_client = HomeboxClient(base_url="http://homebox.test/api/v1", client=upstream_http)
        monkeypatch.setattr(auth_api, "get_client", lambda: homebox_client)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://testserver"
        ) as api_client:
            response = await api_client.post(
                "/api/refresh", headers={"Authorization": "Bearer old-token"}
            )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Homebox returned an invalid token refresh response. Please try again.",
        "code": "HOMEBOX_ERROR",
    }
