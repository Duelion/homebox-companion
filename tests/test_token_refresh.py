"""Unit tests for token refresh response normalization.

Homebox (sysadminsmedia) >= 0.24 returns the refreshed token from
``GET /users/refresh`` in a field named ``raw`` (``UserAuthTokenDetail``),
unlike login which returns ``token`` (``TokenResponse``). These tests pin
the normalization so a "successful" refresh never yields an empty token.
See issue #160.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from homebox_companion.homebox.client import HomeboxClient

pytestmark = pytest.mark.unit


def _client_returning(payload: dict[str, Any]) -> HomeboxClient:
    """Build a HomeboxClient whose transport always returns ``payload``."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    return HomeboxClient(
        base_url="http://homebox.test/api/v1",
        client=httpx.AsyncClient(transport=transport),
    )


@pytest.mark.asyncio
async def test_refresh_token_normalizes_raw_field_to_token() -> None:
    """Homebox >=0.24 refresh responses carry the token in ``raw``."""
    client = _client_returning(
        {
            "raw": "new-token-from-homebox",
            "attachmentToken": "att",
            "expiresAt": "2026-08-25T00:00:00Z",
        }
    )
    async with client:
        data = await client.refresh_token("old-token")

    assert data.get("token") == "new-token-from-homebox"


@pytest.mark.asyncio
async def test_refresh_token_keeps_legacy_token_field_and_strips_bearer() -> None:
    """Legacy refresh responses with a ``token`` field keep working."""
    client = _client_returning({"token": "Bearer legacy-token", "expiresAt": "2026-08-25T00:00:00Z"})
    async with client:
        data = await client.refresh_token("old-token")

    assert data.get("token") == "legacy-token"
