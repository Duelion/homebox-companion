"""Workers AI Gemma profile options remain opt-in and provider-specific."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from homebox_companion.core import persistent_settings as storage
from homebox_companion.core.llm_router import _build_router_from_profiles
from homebox_companion.core.llm_utils import workers_ai_gemma_options
from server.api.llm_profiles import router
from server.dependencies import require_auth

MODEL = "openai/@cf/google/gemma-4-26b-a4b-it"
API_BASE = "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/v1"
OPTIONS = {"chat_template_kwargs": {"enable_thinking": False}}


@pytest.fixture
def isolated_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(storage, "SETTINGS_FILE", tmp_path / "settings.yaml")
    storage.clear_settings_cache()
    yield
    storage.clear_settings_cache()


@pytest.mark.parametrize(
    ("model", "base", "enabled"),
    [
        (MODEL, API_BASE, False),
        (MODEL, "https://example.org/v1", True),
        ("openai/@cf/openai/gpt-oss-20b", API_BASE, True),
    ],
)
def test_only_opted_in_direct_gemma_profiles_receive_options(model: str, base: str, enabled: bool) -> None:
    assert workers_ai_gemma_options(model, base, enabled) == {}


@pytest.mark.parametrize("gemma_role", ["primary", "fallback"])
def test_opt_in_survives_profile_updates_and_configures_only_the_gemma_deployment(
    isolated_profiles: None, gemma_role: str
) -> None:
    other_role = "fallback" if gemma_role == "primary" else "primary"
    storage.save_settings(
        storage.PersistentSettings(
            llm_profiles=[
                storage.ModelProfile(
                    name="other",
                    model="gpt-5.6-luna",
                    status=storage.ProfileStatus.PRIMARY,
                )
            ]
        )
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: None

    with TestClient(app) as client:
        profile = client.post(
            "/llm/profiles",
            json={
                "name": "gemma",
                "model": MODEL,
                "api_base": API_BASE,
                "api_key": "sample-cloudflare-token",
                "status": gemma_role,
                "disable_workers_ai_gemma_thinking": True,
            },
        )
        assert profile.status_code == 201
        assert profile.json()["disable_workers_ai_gemma_thinking"] is True
        assert "api_key" not in profile.json()
        if gemma_role == "primary":
            assert client.put("/llm/profiles/other", json={"status": other_role}).status_code == 200

        update = client.put("/llm/profiles/gemma", json={"api_base": API_BASE + "/"})
        assert update.json()["disable_workers_ai_gemma_thinking"] is True
        saved = next(profile for profile in storage.load_settings().llm_profiles if profile.name == "gemma")
        assert saved.disable_workers_ai_gemma_thinking

        with patch("homebox_companion.core.llm_router.Router") as mock_router:
            _build_router_from_profiles()
        deployments = {
            entry["model_name"]: entry["litellm_params"] for entry in mock_router.call_args.kwargs["model_list"]
        }
        assert deployments[gemma_role]["extra_body"] == OPTIONS
        assert "extra_body" not in deployments[other_role]

        cleared = client.put("/llm/profiles/gemma", json={"disable_workers_ai_gemma_thinking": False})
        assert cleared.json()["disable_workers_ai_gemma_thinking"] is False
        saved = next(profile for profile in storage.load_settings().llm_profiles if profile.name == "gemma")
        assert not saved.disable_workers_ai_gemma_thinking
