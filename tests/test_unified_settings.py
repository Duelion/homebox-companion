"""Unified preference storage migrations, effective values and transactions."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI
from pydantic import SecretStr

from homebox_companion.core import field_preferences as preferences
from homebox_companion.core import persistent_settings as storage
from server.api import custom_fields, field_preferences, llm_profiles
from server.dependencies import require_auth


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(storage, "SETTINGS_FILE", tmp_path / "data" / "settings.yaml")
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", tmp_path / "legacy.json")
    monkeypatch.setattr(
        preferences.FieldPreferences, "model_config", preferences.FieldPreferences.model_config | {"env_file": None}
    )
    storage.clear_settings_cache()
    preferences.get_defaults.cache_clear()
    yield
    storage.clear_settings_cache()
    preferences.get_defaults.cache_clear()


def existing_yaml(version: int = 2) -> bytes:
    """Create an old store with real settings and a stale preference snapshot."""
    storage.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(
        {
            "version": version,
            "llm_profiles": [
                {"name": "saved", "model": "gpt-5.6-luna", "status": "primary", "api_key": "saved-secret"}
            ],
            "custom_fields": [{"name": "Material", "ai_instruction": "Preserve steel"}],
            "field_preferences": {"name": "stale bootstrap", "default_tag_id": "stale-tag"},
        }
    ).encode()
    storage.SETTINGS_FILE.write_bytes(content)
    return content


@pytest.mark.parametrize("version", [None, 1, 2])
def test_legacy_json_is_authoritative_and_migrated_once(version: int | None) -> None:
    if version is not None:
        existing_yaml(version)
    legacy = {"default_label_id": "retained-tag", "name": "Unicode — 鋼", "notes": None}
    original = json.dumps(legacy).encode()
    preferences.PREFERENCES_FILE.write_bytes(original)

    loaded = storage.load_settings()

    assert loaded.version == 3
    assert loaded.field_preferences == {"default_tag_id": "retained-tag", "name": "Unicode — 鋼"}
    if version is not None:
        assert loaded.llm_profiles[0].api_key == SecretStr("saved-secret")
        assert loaded.custom_fields[0].name == "Material"
    assert preferences.PREFERENCES_FILE.read_bytes() == original
    # Reset never deletes other settings or reimports the preserved legacy copy.
    before = loaded.model_dump(exclude={"field_preferences"})
    preferences.reset_field_preferences()
    storage.clear_settings_cache()
    assert storage.load_settings().field_preferences == {}
    assert storage.load_settings().model_dump(exclude={"field_preferences"}) == before
    assert preferences.PREFERENCES_FILE.read_bytes() == original


@pytest.mark.parametrize("version", [1, 2])
def test_absent_legacy_json_does_not_activate_stale_yaml(version: int) -> None:
    existing_yaml(version)
    loaded = storage.load_settings()
    assert loaded.version == 3
    assert loaded.field_preferences == {}
    assert loaded.llm_profiles[0].name == "saved"
    assert loaded.custom_fields[0].name == "Material"


def test_fresh_store_is_sparse_and_env_changes_survive_subsequent_startups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "French")
    monkeypatch.setenv("HBC_AI_DEFAULT_TAG_ID", "env-tag-one")
    assert storage.load_settings().field_preferences == {}
    assert preferences.load_field_preferences().default_tag_id == "env-tag-one"
    preferences.save_field_preferences(preferences.FieldPreferences(name="saved naming"))
    assert storage.load_settings().field_preferences == {"name": "saved naming"}

    monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "German")
    monkeypatch.setenv("HBC_AI_DEFAULT_TAG_ID", "env-tag-two")
    preferences.get_defaults.cache_clear()
    storage.clear_settings_cache()
    effective = preferences.load_field_preferences()
    assert effective.output_language == "German"
    assert effective.default_tag_id == "env-tag-two"
    assert effective.name == "saved naming"
    preferences.save_field_preferences(
        preferences.FieldPreferences(output_language="Spanish", default_tag_id="saved-tag")
    )

    monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "Italian")
    monkeypatch.setenv("HBC_AI_DEFAULT_TAG_ID", "env-tag-three")
    preferences.get_defaults.cache_clear()
    storage.clear_settings_cache()
    assert preferences.load_field_preferences().output_language == "Spanish"
    assert preferences.load_field_preferences().default_tag_id == "saved-tag"


@pytest.mark.asyncio
async def test_sparse_api_values_drive_effective_prompt_and_reset() -> None:
    from homebox_companion.tools.vision.prompts import build_detection_system_prompt

    app = FastAPI()
    app.include_router(field_preferences.router, prefix="/api")
    app.dependency_overrides[require_auth] = lambda: None
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        saved = await client.put(
            "/api/settings/field-preferences",
            json={
                "output_language": "Spanish",
                "default_tag_id": "selected-tag",
                "name": "Use unique naming — 鋼",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["description"] is None
        assert saved.json()["name"] == "Use unique naming — 鋼"
        effective = preferences.load_field_preferences()
        prompt = build_detection_system_prompt(
            tags=[],
            field_preferences=effective.get_effective_customizations(),
            output_language=effective.output_language,
        )
        assert "Use unique naming — 鋼" in prompt
        assert "Spanish" in prompt
        assert effective.default_tag_id == "selected-tag"
        reset = await client.delete("/api/settings/field-preferences")
        assert reset.status_code == 200
        assert all(value is None for value in reset.json().values())
    assert storage.load_settings().field_preferences == {}


@pytest.mark.parametrize("legacy", ["{secret: malformed", "[]", '{"name":42}'])
@pytest.mark.parametrize("version", [None, 2])
def test_invalid_legacy_fails_closed_preserving_both_files(legacy: str, version: int | None) -> None:
    original_yaml = existing_yaml(version) if version is not None else None
    original_legacy = legacy.encode()
    preferences.PREFERENCES_FILE.write_bytes(original_legacy)
    with pytest.raises(storage.SettingsLoadError, match="legacy field preferences") as caught:
        preferences.load_field_preferences()
    assert "secret" not in str(caught.value)
    assert caught.value.__context__ is None
    assert preferences.PREFERENCES_FILE.read_bytes() == original_legacy
    if original_yaml is None:
        assert not storage.SETTINGS_FILE.exists()
    else:
        assert storage.SETTINGS_FILE.read_bytes() == original_yaml


@pytest.mark.parametrize("version", [2, 3])
def test_corrupt_yaml_is_never_overwritten_by_preferences(version: int) -> None:
    storage.SETTINGS_FILE.parent.mkdir()
    original = f"version: {version}\nllm_profiles: [secret malformed".encode()
    storage.SETTINGS_FILE.write_bytes(original)
    preferences.PREFERENCES_FILE.write_text('{"name":"legacy"}')
    for operation in (preferences.load_field_preferences, preferences.reset_field_preferences):
        with pytest.raises(storage.SettingsLoadError):
            operation()
        assert storage.SETTINGS_FILE.read_bytes() == original


@pytest.mark.parametrize("version", [None, 2])
def test_failed_migration_replace_preserves_sources_and_does_not_cache_success(
    version: int | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = existing_yaml(version) if version is not None else None
    preferences.PREFERENCES_FILE.write_text('{"name":"legacy naming"}')
    replace = storage.os.replace

    def fail(*args: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises((storage.SettingsLoadError, OSError)):
        preferences.load_field_preferences()
    if original is None:
        assert not storage.SETTINGS_FILE.exists()
    else:
        assert storage.SETTINGS_FILE.read_bytes() == original
    assert preferences.PREFERENCES_FILE.read_text() == '{"name":"legacy naming"}'
    assert list(storage.SETTINGS_FILE.parent.glob("*.tmp")) == []
    monkeypatch.setattr(storage.os, "replace", replace)
    assert preferences.load_field_preferences().name == "legacy naming"
    assert storage.load_settings().version == 3


def test_failed_preference_save_preserves_all_settings_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    preferences.save_field_preferences(preferences.FieldPreferences(name="saved naming"))
    original = storage.SETTINGS_FILE.read_bytes()
    assert preferences.load_field_preferences().name == "saved naming"

    def fail(*args: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(OSError, match="replace failed"):
        preferences.save_field_preferences(preferences.FieldPreferences(name="unsaved naming"))
    assert storage.SETTINGS_FILE.read_bytes() == original
    assert preferences.load_field_preferences().name == "saved naming"


def test_all_runtime_writers_serialize_fresh_read_through_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    storage.save_settings(
        storage.PersistentSettings(
            llm_profiles=[
                storage.ModelProfile(name="primary", model="gpt-5.6-luna", status=storage.ProfileStatus.PRIMARY),
            ]
        )
    )
    first_mutation = threading.Event()
    release_first = threading.Event()
    attempted = [threading.Event(), threading.Event()]
    observed: list[dict[str, str]] = []
    real_mutate = storage.mutate_settings

    def wrapped_mutate(mutate):
        def wrapped(candidate):
            observed.append(dict(candidate.field_preferences))
            if threading.current_thread().name.endswith("_0"):
                first_mutation.set()
                assert release_first.wait(5)
            mutate(candidate)

        return real_mutate(wrapped)

    monkeypatch.setattr(storage, "mutate_settings", wrapped_mutate)
    monkeypatch.setattr(custom_fields, "mutate_settings", wrapped_mutate)
    monkeypatch.setattr(llm_profiles, "mutate_settings", wrapped_mutate)

    def update_custom() -> None:
        attempted[0].set()
        asyncio.run(
            custom_fields.update_custom_fields(
                [
                    storage.CustomFieldDefinition(name="Material", ai_instruction="steel"),
                ]
            )
        )

    def update_profile() -> None:
        attempted[1].set()
        asyncio.run(llm_profiles.update_profile("primary", llm_profiles.ProfileUpdateRequest(new_name="renamed")))

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="settings") as pool:
        first = pool.submit(preferences.save_field_preferences, preferences.FieldPreferences(name="durable naming"))
        assert first_mutation.wait(5)
        others = [pool.submit(update_custom), pool.submit(update_profile)]
        try:
            assert all(event.wait(5) for event in attempted)
            for future in others:
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.05)
        finally:
            release_first.set()
        for future in [first, *others]:
            future.result(timeout=5)
    final = storage.load_settings()
    assert observed == [{}, {"name": "durable naming"}, {"name": "durable naming"}]
    assert final.field_preferences == {"name": "durable naming"}
    assert final.llm_profiles[0].name == "renamed"
    assert final.custom_fields[0].name == "Material"
