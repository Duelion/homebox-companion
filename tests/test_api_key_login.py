"""Unit tests for Homebox API key login.

Covers the ``hb_``-prefixed API key flow:
- ``HomeboxClient.validate_api_key`` behavior (mocked HTTP layer)
- ``POST /api/login/api-key`` route behavior (mocked client via dependency overrides)

API keys are long-lived Homebox credentials sent through the same
``Authorization: Bearer`` header as session tokens. Unlike session JWTs they
can never be refreshed nor logged out, so the companion returns
``auth_type="api_key"`` to gate those flows.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from homebox_companion.core.exceptions import (
    HomeboxAuthError,
    HomeboxCompanionError,
    HomeboxConnectionError,
    HomeboxTimeoutError,
)
from homebox_companion.homebox.client import HomeboxClient

# Unit tests only (no external services)
pytestmark = pytest.mark.unit

VALID_KEY = "hb_" + "A" * 43

TEST_USER: dict[str, Any] = {
    "id": "user-123",
    "groupId": "group-123",
    "name": "Demo User",
    "email": "demo@example.com",
    "role": "user",
}


# =============================================================================
# HomeboxClient.validate_api_key
# =============================================================================


class _FakeAsyncClient:
    """Minimal httpx.AsyncClient stand-in that records GET calls."""

    def __init__(self, result: httpx.Response | Exception) -> None:
        self.result = result
        self.requests: list[dict[str, object]] = []

    async def get(self, url: str, headers: dict[str, str] | None = None, **kwargs: object) -> httpx.Response:
        self.requests.append({"url": url, "headers": headers or {}})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class TestValidateApiKey:
    """HomeboxClient.validate_api_key should probe /users/self with the key."""

    async def _client(self, result: httpx.Response | Exception) -> tuple[HomeboxClient, _FakeAsyncClient]:
        fake = _FakeAsyncClient(result)
        client = HomeboxClient(base_url="http://homebox/api/v1", client=fake)  # ty: ignore[invalid-argument-type]
        return client, fake

    @pytest.mark.asyncio
    async def test_valid_key_returns_user_profile(self) -> None:
        client, fake = await self._client(httpx.Response(200, json=TEST_USER))

        result = await client.validate_api_key(VALID_KEY)

        assert result == TEST_USER
        assert fake.requests[0]["url"] == "http://homebox/api/v1/users/self"
        assert fake.requests[0]["headers"] == {
            "Accept": "application/json",
            "Authorization": f"Bearer {VALID_KEY}",
        }

    @pytest.mark.asyncio
    async def test_invalid_key_raises_auth_error(self) -> None:
        client, _fake = await self._client(httpx.Response(401, json={"error": "invalid API key"}))

        with pytest.raises(HomeboxAuthError):
            await client.validate_api_key(VALID_KEY)

    @pytest.mark.asyncio
    async def test_connection_error_raises_connection_error(self) -> None:
        client, _fake = await self._client(httpx.ConnectError("connection refused"))

        with pytest.raises(HomeboxConnectionError):
            await client.validate_api_key(VALID_KEY)

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self) -> None:
        client, _fake = await self._client(httpx.TimeoutException("timed out"))

        with pytest.raises(HomeboxTimeoutError):
            await client.validate_api_key(VALID_KEY)

    @pytest.mark.asyncio
    async def test_server_error_raises_api_error(self) -> None:
        from homebox_companion.core.exceptions import HomeboxAPIError

        client, _fake = await self._client(httpx.Response(500, json={"error": "boom"}))

        with pytest.raises(HomeboxAPIError):
            await client.validate_api_key(VALID_KEY)


# =============================================================================
# POST /api/login/api-key route
# =============================================================================


class _MockValidateClient:
    """HomeboxClient stand-in that returns TEST_USER for valid keys and raises otherwise."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def validate_api_key(self, api_key: str) -> dict[str, Any]:
        self.calls.append(api_key)
        if api_key != VALID_KEY:
            raise HomeboxAuthError("Validate API key failed: {'error': 'invalid API key'}")
        return TEST_USER


class TestApiKeyLoginRoute:
    """POST /api/login/api-key should validate the key and describe a non-refreshable session."""

    @pytest.fixture
    def api_key_test_client(self, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, _MockValidateClient]:
        import server.api.auth as auth_module

        mock = _MockValidateClient()

        # Bump the shared in-memory rate limit high enough for the whole module.
        monkeypatch.setattr(auth_module.settings, "auth_rate_limit_rpm", 1000)
        # The auth routes call get_client() directly (not via Depends), so patch the module name.
        monkeypatch.setattr(auth_module, "get_client", lambda: mock)

        app = FastAPI()
        app.include_router(auth_module.router, prefix="/api")

        @app.exception_handler(HomeboxCompanionError)
        async def domain_error_handler(request: object, exc: HomeboxCompanionError) -> JSONResponse:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.user_message, "code": exc.error_code},
            )

        return TestClient(app), mock

    def test_valid_api_key_logs_in(self, api_key_test_client: tuple[TestClient, _MockValidateClient]) -> None:
        client, mock = api_key_test_client

        response = client.post("/api/login/api-key", json={"api_key": VALID_KEY})

        assert response.status_code == 200
        assert response.json() == {
            "token": VALID_KEY,
            "expires_at": "",
            "auth_type": "api_key",
            "email": "demo@example.com",
            "message": "Login successful",
        }
        assert mock.calls == [VALID_KEY]

    def test_api_key_is_trimmed(self, api_key_test_client: tuple[TestClient, _MockValidateClient]) -> None:
        client, mock = api_key_test_client

        response = client.post("/api/login/api-key", json={"api_key": f"  {VALID_KEY}  "})

        assert response.status_code == 200
        assert response.json()["token"] == VALID_KEY
        assert mock.calls == [VALID_KEY]

    def test_non_hb_key_is_rejected(self, api_key_test_client: tuple[TestClient, _MockValidateClient]) -> None:
        client, mock = api_key_test_client

        response = client.post("/api/login/api-key", json={"api_key": "not-an-api-key"})

        assert response.status_code == 400
        assert mock.calls == []

    def test_invalid_key_returns_401(self, api_key_test_client: tuple[TestClient, _MockValidateClient]) -> None:
        client, _mock = api_key_test_client

        response = client.post("/api/login/api-key", json={"api_key": "hb_" + "B" * 43})

        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_FAILED"

    def test_missing_key_field_is_422(self, api_key_test_client: tuple[TestClient, _MockValidateClient]) -> None:
        client, _mock = api_key_test_client

        response = client.post("/api/login/api-key", json={})

        assert response.status_code == 422
