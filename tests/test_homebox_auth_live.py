"""Auth-source and lifecycle contracts against the disposable Homebox server."""

from __future__ import annotations

import pytest
from conftest import HomeboxAuth

from homebox_companion import HomeboxClient

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_invalid_bearer_cannot_reuse_an_authenticated_session(
    homebox_client: HomeboxClient, homebox_auth: HomeboxAuth,
) -> None:
    """Both auth modes must fail with a bad header even after a successful call."""
    assert await homebox_client.validate_token(homebox_auth.token)
    assert not await homebox_client.validate_token("invalid-test-credential")


class TestAPIKeyLifecycle:
    """Override only the mode; provisioning and client lifecycle remain shared."""

    @pytest.fixture
    def homebox_auth_mode(self) -> str:
        return "api_key"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "endpoint"),
        [pytest.param("GET", "/users/refresh", id="refresh"), pytest.param("POST", "/users/logout", id="logout")],
    )
    async def test_api_keys_reject_session_lifecycle_operations(
        self, homebox_client: HomeboxClient, homebox_auth: HomeboxAuth, method: str, endpoint: str,
    ) -> None:
        """Unsupported session operations must not revoke or replace a valid API key."""
        response = await homebox_client.client.request(
            method, f"{homebox_client.base_url}{endpoint}",
            headers={"Authorization": f"Bearer {homebox_auth.token}"},
        )
        assert response.status_code == 400
        assert await homebox_client.validate_token(homebox_auth.token)
