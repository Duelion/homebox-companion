"""Profile and custom-field settings reject invalid persisted states."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from homebox_companion.core.persistent_settings import ModelProfile, PersistentSettings, ProfileStatus
from server.api import custom_fields, llm_profiles
from server.dependencies import require_auth


@asynccontextmanager
async def settings_client() -> AsyncIterator[httpx.AsyncClient]:
    app = FastAPI()
    app.include_router(llm_profiles.router, prefix="/api")
    app.include_router(custom_fields.router, prefix="/api")
    app.dependency_overrides[require_auth] = lambda: None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def profile_disk(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    disk: dict[str, object] = {
        "settings": PersistentSettings(
            llm_profiles=[ModelProfile(name="first", model="gpt-5.6-luna", status=ProfileStatus.PRIMARY)]
        ),
        "writes": 0,
    }

    def load() -> PersistentSettings:
        settings = disk["settings"]
        assert isinstance(settings, PersistentSettings)
        return settings.model_copy(deep=True)

    def save(settings: PersistentSettings) -> None:
        disk["settings"] = settings.model_copy(deep=True)
        writes = disk["writes"]
        assert isinstance(writes, int)
        disk["writes"] = writes + 1

    monkeypatch.setattr(llm_profiles, "load_settings", load)
    monkeypatch.setattr(llm_profiles, "save_settings", save)
    monkeypatch.setattr(llm_profiles, "clear_settings_cache", lambda: None)
    return disk


@pytest.mark.asyncio
async def test_primary_create_replaces_old_primary_and_fallback_create_replaces_old_fallback(profile_disk) -> None:
    async with settings_client() as client:
        primary = await client.post(
            "/api/llm/profiles", json={"name": "second", "model": "gpt-5-nano", "status": "primary"}
        )
        first_fallback = await client.post(
            "/api/llm/profiles", json={"name": "backup-one", "model": "gpt-5-nano", "status": "fallback"}
        )
        second_fallback = await client.post(
            "/api/llm/profiles", json={"name": "backup-two", "model": "gpt-5-nano", "status": "fallback"}
        )
    assert [primary.status_code, first_fallback.status_code, second_fallback.status_code] == [201, 201, 201]
    settings = profile_disk["settings"]
    assert isinstance(settings, PersistentSettings)
    assert [(p.name, p.status) for p in settings.llm_profiles] == [
        ("first", ProfileStatus.OFF),
        ("second", ProfileStatus.PRIMARY),
        ("backup-one", ProfileStatus.OFF),
        ("backup-two", ProfileStatus.FALLBACK),
    ]


@pytest.mark.asyncio
async def test_sole_primary_cannot_be_disabled_and_secret_is_not_echoed(profile_disk) -> None:
    async with settings_client() as client:
        response = await client.put(
            "/api/llm/profiles/first", json={"status": "off", "api_key": "synthetic-secret-value"}
        )
    assert response.status_code == 400
    assert "synthetic-secret-value" not in response.text
    assert profile_disk["writes"] == 0
    settings = profile_disk["settings"]
    assert isinstance(settings, PersistentSettings)
    assert settings.llm_profiles[0].status == ProfileStatus.PRIMARY
    assert settings.llm_profiles[0].api_key is None


@pytest.mark.asyncio
async def test_invalid_status_is_rejected_without_writing(profile_disk) -> None:
    async with settings_client() as client:
        create = await client.post(
            "/api/llm/profiles", json={"name": "invalid", "model": "gpt-5-nano", "status": "active"}
        )
        update = await client.put("/api/llm/profiles/first", json={"status": "active"})
    assert create.status_code == update.status_code == 422
    assert profile_disk["writes"] == 0


@pytest.mark.asyncio
async def test_valid_activation_and_deletion_preserve_single_primary(profile_disk) -> None:
    async with settings_client() as client:
        created = await client.post("/api/llm/profiles", json={"name": "second", "model": "gpt-5-nano"})
        activated = await client.post("/api/llm/profiles/second/activate")
        deleted = await client.delete("/api/llm/profiles/second")
    assert [created.status_code, activated.status_code, deleted.status_code] == [201, 200, 204]
    settings = profile_disk["settings"]
    assert isinstance(settings, PersistentSettings)
    assert [(p.name, p.status) for p in settings.llm_profiles] == [("first", ProfileStatus.PRIMARY)]


@pytest.mark.asyncio
@pytest.mark.parametrize("names", [["Quantity"], ["A-B", "A B"], ["model_dump"]])
async def test_custom_field_conflicts_are_rejected_without_writing(
    names: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = PersistentSettings()
    writes: list[PersistentSettings] = []
    monkeypatch.setattr(custom_fields, "get_settings", lambda: settings)
    monkeypatch.setattr(custom_fields, "save_settings", writes.append)
    async with settings_client() as client:
        response = await client.put(
            "/api/settings/custom-fields",
            json=[{"name": name, "ai_instruction": "Example"} for name in names],
        )
    assert response.status_code == 400
    assert writes == []
    assert settings.custom_fields == []
