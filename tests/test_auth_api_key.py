"""Tests for Homebox API key authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from homebox_companion.homebox.auth_utils import API_KEY_MIN_LEN, is_homebox_api_key
from server.api import auth as auth_module
from server.dependencies import get_client, get_token

VALID_API_KEY = "hb_" + "A" * (API_KEY_MIN_LEN - 3)
SESSION_TOKEN = "session-token-value"


class _MockHomeboxClient:
    """Mock Homebox client for auth route tests."""

    def __init__(self) -> None:
        self.login = AsyncMock()
        self.login_with_api_key = AsyncMock(
            return_value={"token": VALID_API_KEY, "email": "user@example.com"}
        )
        self.refresh_token = AsyncMock(
            return_value={"token": "new-session-token", "expiresAt": "2099-01-01T00:00:00Z"}
        )
        self.logout = AsyncMock()
        self.get_status = AsyncMock(
            return_value={
                "oidc": {
                    "enabled": True,
                    "allowLocal": False,
                    "buttonText": "Sign in with SSO",
                    "autoRedirect": False,
                }
            }
        )


@pytest.fixture
def auth_client() -> tuple[TestClient, _MockHomeboxClient]:
    mock = _MockHomeboxClient()
    app = FastAPI()
    app.include_router(auth_module.router, prefix="/api")
    app.dependency_overrides[get_client] = lambda: mock  # type: ignore[return-value]
    return TestClient(app), mock


class TestIsHomeboxApiKey:
    def test_valid_key(self) -> None:
        assert is_homebox_api_key(VALID_API_KEY)

    def test_wrong_prefix(self) -> None:
        assert not is_homebox_api_key("xx_" + "A" * 43)

    def test_too_short(self) -> None:
        assert not is_homebox_api_key("hb_short")

    def test_bearer_prefix_not_valid(self) -> None:
        assert not is_homebox_api_key("Bearer " + VALID_API_KEY)


class TestApiKeyLogin:
    def test_api_key_login_success(self, auth_client: tuple[TestClient, _MockHomeboxClient]) -> None:
        client, mock = auth_client
        response = client.post("/api/login", json={"api_key": VALID_API_KEY})
        assert response.status_code == 200
        data = response.json()
        assert data["auth_method"] == "api_key"
        assert data["token"] == VALID_API_KEY
        assert data["expires_at"] is None
        assert data["user_email"] == "user@example.com"
        mock.login_with_api_key.assert_awaited_once_with(VALID_API_KEY)
        mock.login.assert_not_called()

    def test_invalid_api_key_format_returns_422(
        self, auth_client: tuple[TestClient, _MockHomeboxClient]
    ) -> None:
        client, mock = auth_client
        response = client.post("/api/login", json={"api_key": "not-a-key"})
        assert response.status_code == 422
        mock.login_with_api_key.assert_not_called()

    def test_password_and_api_key_mutually_exclusive(
        self, auth_client: tuple[TestClient, _MockHomeboxClient]
    ) -> None:
        client, mock = auth_client
        response = client.post(
            "/api/login",
            json={"username": "a@b.com", "password": "secret", "api_key": VALID_API_KEY},
        )
        assert response.status_code == 422
        mock.login.assert_not_called()
        mock.login_with_api_key.assert_not_called()

    def test_password_login_returns_session_auth_method(
        self, auth_client: tuple[TestClient, _MockHomeboxClient]
    ) -> None:
        client, mock = auth_client
        mock.login.return_value = {
            "token": SESSION_TOKEN,
            "expiresAt": "2099-06-01T12:00:00Z",
        }
        response = client.post(
            "/api/login",
            json={"username": "demo@example.com", "password": "demo"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auth_method"] == "session"
        assert data["token"] == SESSION_TOKEN
        assert data["expires_at"] == "2099-06-01T12:00:00Z"


class TestApiKeyRefreshLogout:
    def test_refresh_rejects_api_key(self, auth_client: tuple[TestClient, _MockHomeboxClient]) -> None:
        client, mock = auth_client
        app = client.app
        app.dependency_overrides[get_token] = lambda: VALID_API_KEY  # type: ignore[assignment]

        response = client.post(
            "/api/refresh",
            headers={"Authorization": f"Bearer {VALID_API_KEY}"},
        )
        assert response.status_code == 400
        assert "do not require refresh" in response.json()["detail"].lower()
        mock.refresh_token.assert_not_called()

    def test_logout_skips_homebox_for_api_key(
        self, auth_client: tuple[TestClient, _MockHomeboxClient]
    ) -> None:
        client, mock = auth_client
        app = client.app
        app.dependency_overrides[get_token] = lambda: VALID_API_KEY  # type: ignore[assignment]

        response = client.post(
            "/api/logout",
            headers={"Authorization": f"Bearer {VALID_API_KEY}"},
        )
        assert response.status_code == 204
        mock.logout.assert_not_called()

    def test_logout_calls_homebox_for_session_token(
        self, auth_client: tuple[TestClient, _MockHomeboxClient]
    ) -> None:
        client, mock = auth_client
        app = client.app
        app.dependency_overrides[get_token] = lambda: SESSION_TOKEN  # type: ignore[assignment,misc]

        response = client.post(
            "/api/logout",
            headers={"Authorization": f"Bearer {SESSION_TOKEN}"},
        )
        assert response.status_code == 204
        mock.logout.assert_awaited_once_with(SESSION_TOKEN)


class TestConfigOidcProxy:
    def test_config_includes_homebox_oidc(self, auth_client: tuple[TestClient, _MockHomeboxClient]) -> None:
        from server.api import config as config_module
        from server.dependencies import get_client as config_get_client

        mock = auth_client[1]
        config_module._status_cache = None
        config_module._status_cache_at = 0.0

        app = FastAPI()
        app.include_router(config_module.router, prefix="/api")
        app.dependency_overrides[config_get_client] = lambda: mock  # type: ignore[return-value]

        client = TestClient(app)
        response = client.get("/api/config")
        assert response.status_code == 200
        oidc = response.json().get("homebox_oidc")
        assert oidc is not None
        assert oidc["enabled"] is True
        assert oidc["allow_local"] is False
        assert oidc["button_text"] == "Sign in with SSO"

    def test_config_oidc_null_when_status_fails(
        self, auth_client: tuple[TestClient, _MockHomeboxClient]
    ) -> None:
        from server.api import config as config_module
        from server.dependencies import get_client as config_get_client

        mock = auth_client[1]
        mock.get_status = AsyncMock(side_effect=RuntimeError("unreachable"))

        app = FastAPI()
        app.include_router(config_module.router, prefix="/api")
        app.dependency_overrides[config_get_client] = lambda: mock  # type: ignore[return-value]

        # Clear config module cache so we hit get_status again
        config_module._status_cache = None
        config_module._status_cache_at = 0.0

        client = TestClient(app)
        response = client.get("/api/config")
        assert response.status_code == 200
        assert response.json().get("homebox_oidc") is None
