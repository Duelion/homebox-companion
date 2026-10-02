"""Failure-path tests for durable persistent settings storage."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from loguru import logger

from homebox_companion.core import persistent_settings
from homebox_companion.core.persistent_settings import (
    PersistentSettings,
    SettingsLoadError,
)


@pytest.fixture
def settings_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "settings.yaml"
    monkeypatch.setattr(persistent_settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(persistent_settings, "SETTINGS_FILE", path)
    return path


def test_failed_write_preserves_existing_settings(settings_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = "version: 2\ncustom_fields: []\n"
    settings_path.write_text(original, encoding="utf-8")
    real_fdopen = os.fdopen

    class FailingWriter:
        def __init__(self, descriptor: int) -> None:
            self.file = real_fdopen(descriptor, "w", encoding="utf-8")

        def __enter__(self) -> FailingWriter:
            return self

        def __exit__(self, *args: object) -> None:
            self.file.close()

        def write(self, content: str) -> None:
            del content
            raise OSError("disk full")

    monkeypatch.setattr(
        persistent_settings.os,
        "fdopen",
        lambda descriptor, *args, **kwargs: FailingWriter(descriptor),
    )

    with pytest.raises(OSError, match="disk full"):
        persistent_settings.save_settings(PersistentSettings())

    assert settings_path.read_text(encoding="utf-8") == original
    assert list(settings_path.parent.glob(".settings.yaml.*.tmp")) == []


def test_failed_replace_preserves_existing_settings(settings_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = "version: 2\ncustom_fields: []\n"
    settings_path.write_text(original, encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("replace failed")

    monkeypatch.setattr(persistent_settings.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        persistent_settings.save_settings(PersistentSettings())

    assert settings_path.read_text(encoding="utf-8") == original
    assert list(settings_path.parent.glob(".settings.yaml.*.tmp")) == []


def test_corrupt_existing_settings_raises_without_overwriting(settings_path: Path) -> None:
    corrupt = "llm_profiles: [unterminated\n"
    settings_path.write_text(corrupt, encoding="utf-8")

    with pytest.raises(SettingsLoadError, match="Failed to load existing settings file"):
        persistent_settings.load_settings()

    assert settings_path.read_text(encoding="utf-8") == corrupt


def test_malformed_yaml_does_not_expose_saved_key(settings_path: Path) -> None:
    secret = "SYNTHETIC_SENTINEL_7391"
    settings_path.write_text(f"llm_profiles:\n  - api_key: {secret}: malformed\n", encoding="utf-8")
    messages = []
    sink = logger.add(messages.append, format="{message}")
    try:
        with pytest.raises(SettingsLoadError) as caught:
            persistent_settings.load_settings()
    finally:
        logger.remove(sink)

    assert secret not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert all(secret not in str(message) for message in messages)


def test_empty_existing_settings_raises_without_overwriting(settings_path: Path) -> None:
    settings_path.write_text("", encoding="utf-8")

    with pytest.raises(SettingsLoadError, match="settings file is empty"):
        persistent_settings.load_settings()

    assert settings_path.read_text(encoding="utf-8") == ""


def test_missing_settings_bootstraps_and_persists(settings_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bootstrapped = PersistentSettings()
    monkeypatch.setattr(persistent_settings, "bootstrap_from_env", lambda: bootstrapped)

    loaded = persistent_settings.load_settings()

    assert loaded == bootstrapped
    assert settings_path.exists()
    assert persistent_settings.load_settings() == bootstrapped


def test_migration_is_persisted(settings_path: Path) -> None:
    settings_path.write_text(
        "version: 1\nllm_profiles: []\nfield_preferences: {}\n",
        encoding="utf-8",
    )

    loaded = persistent_settings.load_settings()

    assert loaded.version == persistent_settings.CURRENT_VERSION
    persisted = persistent_settings.yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    assert persisted["version"] == persistent_settings.CURRENT_VERSION
    assert persisted["custom_fields"] == []
