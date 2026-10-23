"""Browser AI deadlines and their safe public configuration contract."""

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from homebox_companion.core.config import Settings
from server.app import create_app


@pytest.mark.parametrize(("llm_timeout", "expected"), [(120, 180), (1800, 1860), (0, 60), (86400, 86400)])
def test_default_ai_deadline_tracks_llm_timeout(llm_timeout: int, expected: int) -> None:
    settings = Settings(llm_timeout=llm_timeout)
    assert settings.ai_request_timeout_seconds == expected
    assert settings.llm_timeout == llm_timeout


def test_explicit_ai_deadline_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HBC_AI_REQUEST_TIMEOUT", "7200")
    settings = Settings(llm_timeout=1800)
    assert settings.ai_request_timeout_seconds == 7200
    assert settings.llm_timeout == 1800


@pytest.mark.parametrize("value", ["", "   ", "\t"])
def test_blank_ai_deadline_uses_derived_default(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HBC_AI_REQUEST_TIMEOUT", value)
    settings = Settings(llm_timeout=1800)
    assert settings.ai_request_timeout is None
    assert settings.ai_request_timeout_seconds == 1860


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "invalid", "86401"])
def test_invalid_ai_deadline_is_rejected(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HBC_AI_REQUEST_TIMEOUT", value)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, SecretStr("hb_private-homebox-key")])
async def test_safe_config_exposes_ai_deadline_in_both_auth_modes(api_key: SecretStr | None) -> None:
    settings = Settings(
        homebox_api_key=api_key,
        llm_api_key="private-provider-key",
        ai_request_timeout=2400,
    )
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://companion.test") as client:
        response = await client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["ai_request_timeout_seconds"] == 2400
    assert response.json()["auth_mode"] == ("api_key" if api_key else "legacy")
    assert "private-provider-key" not in response.text
    assert "hb_private-homebox-key" not in response.text
    assert "llm_api_key" not in response.json()
    assert "homebox_api_key" not in response.json()
