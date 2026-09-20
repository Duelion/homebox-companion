"""Browser origin policy for configured Homebox API-key deployments."""

import httpx
import pytest
from pydantic import SecretStr

from homebox_companion.core.config import Settings
from server.app import create_app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origins",
    ["https://allowed.test", "*,https://allowed.test", " https://allowed.test , * "],
)
async def test_explicit_key_mode_origin_survives_wildcard(origins: str) -> None:
    app = create_app(Settings(homebox_api_key=SecretStr("hb_configured"), cors_origins=origins))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://companion.test"
    ) as client:
        allowed = await client.post(
            "/api/logout", headers={"Origin": "https://allowed.test", "X-Companion-Request": "1"}
        )
        # Reaching the key-mode logout handler proves the browser guard admitted it.
        assert allowed.status_code == 409
        assert allowed.headers["access-control-allow-origin"] == "https://allowed.test"

        rejected = await client.post(
            "/api/logout", headers={"Origin": "https://untrusted.test", "X-Companion-Request": "1"}
        )
        assert rejected.status_code == 403
        assert "access-control-allow-origin" not in rejected.headers
