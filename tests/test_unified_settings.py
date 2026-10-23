"""Independent JSON preferences and YAML settings durability."""

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


@pytest.mark.parametrize("version", [1, 2, 3])
def test_json_is_authoritative_and_yaml_snapshot_stays_inactive(version: int) -> None:
    original_yaml = existing_yaml(version)
    original_json = '{"default_label_id":"retained-tag","name":"Unicode — 鋼","notes":null}'.encode()
    preferences.PREFERENCES_FILE.write_bytes(original_json)
    assert preferences.load_field_preferences().name == "Unicode — 鋼"
    assert preferences.load_field_preferences().default_tag_id == "retained-tag"
    assert storage.SETTINGS_FILE.read_bytes() == original_yaml
    assert preferences.PREFERENCES_FILE.read_bytes() == original_json
    loaded = storage.load_settings()
    assert loaded.field_preferences == {"name": "stale bootstrap", "default_tag_id": "stale-tag"}
    assert loaded.llm_profiles[0].api_key == SecretStr("saved-secret")
    assert loaded.custom_fields[0].name == "Material"
    yaml_after_load = storage.SETTINGS_FILE.read_bytes()
    preferences.save_field_preferences(preferences.FieldPreferences(name="updated"))
    preferences.reset_field_preferences()
    assert not preferences.PREFERENCES_FILE.exists()
    assert storage.SETTINGS_FILE.read_bytes() == yaml_after_load
    assert preferences.load_field_preferences().name == preferences.get_defaults().name


def test_fresh_store_is_sparse_and_env_changes_survive_subsequent_startups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HBC_AI_OUTPUT_LANGUAGE", "French")
    monkeypatch.setenv("HBC_AI_DEFAULT_TAG_ID", "env-tag-one")
    assert storage.load_settings().field_preferences == {}
    assert preferences.load_field_preferences().default_tag_id == "env-tag-one"
    preferences.save_field_preferences(preferences.FieldPreferences(name="saved naming"))
    assert json.loads(preferences.PREFERENCES_FILE.read_text()) == {"name": "saved naming"}

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


@pytest.mark.parametrize("invalid", ["{secret: malformed", "[]", '{"name":42}'])
def test_invalid_json_preserves_both_files(invalid: str) -> None:
    original_yaml = existing_yaml()
    preferences.PREFERENCES_FILE.write_text(invalid)
    with pytest.raises(preferences.FieldPreferencesLoadError) as caught:
        preferences.load_field_preferences()
    assert "secret" not in str(caught.value)
    assert caught.value.__context__ is None
    assert preferences.PREFERENCES_FILE.read_text() == invalid
    assert storage.SETTINGS_FILE.read_bytes() == original_yaml
    assert storage.load_settings().llm_profiles[0].name == "saved"


def test_corrupt_yaml_does_not_block_json_preferences() -> None:
    storage.SETTINGS_FILE.parent.mkdir()
    original = b"llm_profiles: [secret malformed"
    storage.SETTINGS_FILE.write_bytes(original)
    preferences.save_field_preferences(preferences.FieldPreferences(name="independent"))
    assert preferences.load_field_preferences().name == "independent"
    preferences.reset_field_preferences()
    assert storage.SETTINGS_FILE.read_bytes() == original


def test_failed_json_replace_preserves_files(monkeypatch: pytest.MonkeyPatch) -> None:
    original_yaml = existing_yaml()
    preferences.save_field_preferences(preferences.FieldPreferences(name="saved naming"))
    original_json = preferences.PREFERENCES_FILE.read_bytes()

    def fail(*args: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(preferences.os, "replace", fail)
    with pytest.raises(OSError, match="replace failed"):
        preferences.save_field_preferences(preferences.FieldPreferences(name="unsaved naming"))
    assert preferences.PREFERENCES_FILE.read_bytes() == original_json
    assert storage.SETTINGS_FILE.read_bytes() == original_yaml
    assert preferences.load_field_preferences().name == "saved naming"
    assert list(preferences.PREFERENCES_FILE.parent.glob("*.tmp")) == []


def test_yaml_writers_serialize_while_json_remains_independent(monkeypatch: pytest.MonkeyPatch) -> None:
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
        first = pool.submit(update_custom)
        assert first_mutation.wait(5)
        preferences.save_field_preferences(preferences.FieldPreferences(name="durable naming"))
        assert preferences.load_field_preferences().name == "durable naming"
        others = [pool.submit(update_profile)]
        try:
            assert attempted[1].wait(5)
            for future in others:
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.05)
        finally:
            release_first.set()
        for future in [first, *others]:
            future.result(timeout=5)
    final = storage.load_settings()
    assert observed == [{}, {}]
    assert final.field_preferences == {}
    assert preferences.load_field_preferences().name == "durable naming"
    assert final.llm_profiles[0].name == "renamed"
    assert final.custom_fields[0].name == "Material"


def test_json_save_and_reset_serialize(monkeypatch: pytest.MonkeyPatch) -> None:
    replacing = threading.Event()
    release = threading.Event()
    resetting = threading.Event()
    real_replace = preferences.os.replace

    def blocked_replace(source: Path, destination: Path) -> None:
        replacing.set()
        assert release.wait(5)
        real_replace(source, destination)

    def reset() -> None:
        resetting.set()
        preferences.reset_field_preferences()

    monkeypatch.setattr(preferences.os, "replace", blocked_replace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        saving = pool.submit(preferences.save_field_preferences, preferences.FieldPreferences(name="saved"))
        assert replacing.wait(5)
        reset_future = pool.submit(reset)
        try:
            assert resetting.wait(5)
            with pytest.raises(TimeoutError):
                reset_future.result(timeout=0.05)
        finally:
            release.set()
        saving.result(timeout=5)
        reset_future.result(timeout=5)
    assert not preferences.PREFERENCES_FILE.exists()
    assert not storage.SETTINGS_FILE.exists()


@pytest.fixture
def linked_preferences(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    link = tmp_path / "config" / "field_preferences.json"
    target = tmp_path / "data" / "config" / "field_preferences.json"
    link.parent.mkdir()
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("File symlinks are unavailable for this runtime user")
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", link)
    return link, target


def test_json_file_symlink_survives_save_reset_and_resave(linked_preferences: tuple[Path, Path]) -> None:
    link, target = linked_preferences
    assert not target.parent.exists()
    preferences.save_field_preferences(preferences.FieldPreferences(name="first"))
    assert link.is_symlink()
    assert json.loads(target.read_text()) == {"name": "first"}
    assert preferences.load_field_preferences().name == "first"
    preferences.reset_field_preferences()
    assert link.is_symlink()
    assert not target.exists()
    assert preferences.load_field_preferences().name == preferences.get_defaults().name
    preferences.save_field_preferences(preferences.FieldPreferences(name="second"))
    assert link.is_symlink()
    assert json.loads(target.read_text()) == {"name": "second"}
    assert preferences.load_field_preferences().name == "second"


def test_failed_replace_preserves_json_file_symlink_and_target(
    linked_preferences: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    link, target = linked_preferences
    preferences.save_field_preferences(preferences.FieldPreferences(name="saved"))
    original = target.read_bytes()

    def fail(source: Path, destination: Path) -> None:
        assert destination == target
        raise OSError("replace failed")

    monkeypatch.setattr(preferences.os, "replace", fail)
    with pytest.raises(OSError, match="replace failed"):
        preferences.save_field_preferences(preferences.FieldPreferences(name="unsaved"))
    assert link.is_symlink()
    assert target.read_bytes() == original
    assert preferences.load_field_preferences().name == "saved"
    assert list(target.parent.glob("*.tmp")) == []


def test_old_full_yaml_snapshot_preserves_null_without_affecting_json() -> None:
    existing_yaml(version=2)
    raw = yaml.safe_load(storage.SETTINGS_FILE.read_text())
    snapshot = preferences.FieldPreferences().model_dump()
    assert snapshot["default_tag_id"] is None
    raw["field_preferences"] = snapshot
    storage.SETTINGS_FILE.write_text(yaml.safe_dump(raw))
    preferences.PREFERENCES_FILE.write_text('{"name":"live JSON","default_tag_id":"live-tag"}')

    loaded = storage.load_settings()
    assert loaded.version == storage.CURRENT_VERSION
    assert loaded.field_preferences == snapshot
    assert loaded.llm_profiles[0].api_key == SecretStr("saved-secret")
    assert loaded.custom_fields[0].name == "Material"
    assert yaml.safe_load(storage.SETTINGS_FILE.read_text())["field_preferences"] == snapshot
    assert preferences.load_field_preferences().name == "live JSON"
    assert preferences.load_field_preferences().default_tag_id == "live-tag"
    before = storage.SETTINGS_FILE.read_bytes()
    preferences.reset_field_preferences()
    assert storage.SETTINGS_FILE.read_bytes() == before
    assert preferences.load_field_preferences().default_tag_id is None
