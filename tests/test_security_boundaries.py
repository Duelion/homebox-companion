"""Regression contracts for local-resource authorization and LLM credentials."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from pydantic import SecretStr

from homebox_companion.core import config, field_preferences, llm_utils
from homebox_companion.core.config import Settings
from homebox_companion.core.llm_security import NO_API_KEY, build_llm_params
from homebox_companion.core.persistent_settings import (
    CustomFieldDefinition,
    ModelProfile,
    PersistentSettings,
    ProfileStatus,
)
from homebox_companion.homebox.client import HomeboxClient
from server.api import custom_fields, llm_profiles, logs
from server.app import create_app


@asynccontextmanager
async def security_client(*, user_id="member", upstream_status=200, api_key=None):
    settings = Settings(
        _env_file=None,
        homebox_api_key=api_key,
    )
    app = create_app(settings)
    requests = []

    def upstream(request):
        requests.append(request)
        assert request.url.path == "/api/v1/users/self"
        return httpx.Response(upstream_status, json={"id": user_id})

    async with HomeboxClient(
        base_url="http://homebox.test/api/v1", transport=httpx.MockTransport(upstream), allow_cookies=False
    ) as homebox:
        app.state.homebox_client = homebox
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://companion.test",
            headers={"Authorization": "Bearer test-session", "X-Companion-Request": "1"},
        ) as client:
            yield client, app, requests


@pytest.fixture
def profile_store(monkeypatch):
    store = PersistentSettings(
        llm_profiles=[
            ModelProfile(
                name="primary",
                model="gpt-5-mini",
                api_key=SecretStr("synthetic-saved-key"),
                api_base="https://provider.test/v1",
                status=ProfileStatus.PRIMARY,
            )
        ]
    )
    save = Mock()
    completion = AsyncMock(return_value=SimpleNamespace(model="gpt-5-mini"))
    monkeypatch.setattr(llm_profiles, "load_settings", lambda: store)
    monkeypatch.setattr(llm_profiles, "clear_settings_cache", lambda: None)
    monkeypatch.setattr(llm_profiles, "save_settings", save)
    monkeypatch.setattr(llm_profiles.litellm, "acompletion", completion)
    return store, save, completion


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/llm/profiles",
        "/api/logs",
        "/api/logs/download",
        "/api/logs/llm-debug",
        "/api/logs/llm-debug/download",
        "/api/settings/field-preferences",
        "/api/settings/custom-fields",
    ],
)
async def test_invalid_token_cannot_access_local_resources(path, profile_store):
    async with security_client(upstream_status=401) as (client, app, requests):
        # A prior successful bootstrap must not authorize a revoked token.
        digest = hashlib.sha256(b"test-session").hexdigest()
        app.state.homebox_identities[digest] = ("member", "group")
        response = await client.get(path)
    assert response.status_code == 401
    assert len(requests) == 1
    profile_store[1].assert_not_called()
    profile_store[2].assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, SecretStr("hb_synthetic-configured")])
@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        ("GET", "/api/llm/profiles", None, 200),
        ("POST", "/api/llm/profiles", {"name": "new", "model": "gpt-5-mini"}, 201),
        ("GET", "/api/logs", None, 200),
        ("GET", "/api/logs/download", None, 200),
        ("GET", "/api/logs/llm-debug", None, 200),
        ("GET", "/api/logs/llm-debug/download", None, 200),
        ("POST", "/api/llm/profiles/primary/test", {}, 200),
        ("POST", "/api/llm/profiles/primary/activate", None, 200),
        ("PUT", "/api/llm/profiles/primary", {"model": "gpt-5-nano"}, 200),
        ("DELETE", "/api/llm/profiles/primary", None, 204),
        ("PUT", "/api/settings/field-preferences", {}, 200),
        ("DELETE", "/api/settings/field-preferences", None, 200),
        ("PUT", "/api/settings/custom-fields", [], 200),
        ("DELETE", "/api/settings/custom-fields/example", None, 200),
    ],
)
async def test_authenticated_user_can_manage_shared_resources(
    method, path, body, status, api_key, profile_store, monkeypatch, tmp_path
):
    store, save, _ = profile_store
    store.custom_fields = [CustomFieldDefinition(name="example", ai_instruction="Example field")]
    monkeypatch.setattr(custom_fields, "get_settings", lambda: store)
    monkeypatch.setattr(custom_fields, "save_settings", save)
    monkeypatch.setattr(field_preferences, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(field_preferences, "PREFERENCES_FILE", tmp_path / "field_preferences.json")
    monkeypatch.setattr(logs, "_LOGS_DIR", str(tmp_path))
    (tmp_path / "homebox_companion_2026-09-20.log").write_text("Test log\n")
    (tmp_path / "llm_debug_2026-09-20.log").write_text("Test LLM log\n")
    async with security_client(api_key=api_key) as (client, _, requests):
        response = await client.request(method, path, json=body)
    assert response.status_code == status, response.text
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, SecretStr("hb_synthetic-configured")])
async def test_authenticated_user_can_list_profiles_without_exposing_secrets(profile_store, api_key):
    async with security_client(api_key=api_key) as (client, _, requests):
        response = await client.get("/api/llm/profiles")
    assert response.status_code == 200
    assert "synthetic-saved-key" not in response.text
    expected = "Bearer hb_synthetic-configured" if api_key else "Bearer test-session"
    assert requests[0].headers["Authorization"] == expected


@pytest.mark.asyncio
async def test_configured_key_must_still_be_valid_for_settings_routes(profile_store):
    async with security_client(api_key=SecretStr("hb_synthetic"), upstream_status=401) as (client, _, _):
        response = await client.get("/api/llm/profiles")
    assert response.status_code == 502
    assert response.json()["code"] == "HOMEBOX_API_KEY_REJECTED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"api_base": "https://different.test/v1"},
        {"api_base": "https://provider.test/another-path"},
        {"model": "anthropic/claude-sonnet-4-20250514"},
    ],
)
@pytest.mark.parametrize("test_connection", [False, True])
async def test_destination_changes_require_explicit_key(overrides, test_connection, profile_store):
    store, save, completion = profile_store
    async with security_client() as (client, _, _):
        method = "POST" if test_connection else "PUT"
        path = "/api/llm/profiles/primary" + ("/test" if test_connection else "")
        response = await client.request(method, path, json=overrides)
    assert response.status_code == 422
    assert store.llm_profiles[0].api_base == "https://provider.test/v1"
    save.assert_not_called()
    completion.assert_not_called()


@pytest.mark.asyncio
async def test_same_provider_model_change_can_use_saved_key(profile_store):
    async with security_client() as (client, _, _):
        response = await client.post("/api/llm/profiles/primary/test", json={"model": "gpt-5-nano"})
    assert response.status_code == 200
    assert profile_store[2].call_args.kwargs["api_key"] == "synthetic-saved-key"


@pytest.mark.asyncio
async def test_explicit_key_is_used_for_new_destination(profile_store):
    async with security_client() as (client, _, _):
        response = await client.post(
            "/api/llm/profiles/primary/test",
            json={
                "api_base": "https://different.test/v1",
                "api_key": "synthetic-new-key",
            },
        )
    assert response.status_code == 200
    assert profile_store[2].call_args.kwargs["api_key"] == "synthetic-new-key"


def test_primary_cannot_inherit_environment_key_for_different_destination(monkeypatch):
    monkeypatch.setattr(
        config,
        "settings",
        Settings(
            _env_file=None,
            llm_model="gpt-5-mini",
            llm_api_key="synthetic-env-key",
            llm_api_base="https://provider.test/v1",
        ),
    )
    monkeypatch.setattr(
        llm_utils,
        "get_primary_profile",
        lambda: ModelProfile(
            name="new",
            model="gpt-5-mini",
            api_base="https://different.test/v1",
        ),
    )
    assert llm_utils.resolve_llm_credentials().api_key is None


def test_fallback_cannot_inherit_primary_key_for_different_destination(monkeypatch):
    from homebox_companion.core import llm_router

    monkeypatch.setattr(
        llm_utils,
        "resolve_llm_credentials",
        lambda: llm_utils.LLMCredentials(
            model="gpt-5-mini",
            api_key="synthetic-primary-key",
            api_base="https://provider.test/v1",
        ),
    )
    monkeypatch.setattr(
        llm_router,
        "get_fallback_profile",
        lambda: ModelProfile(
            name="fallback",
            model="gpt-5-nano",
            api_base="https://different.test/v1",
        ),
    )
    router = Mock()
    monkeypatch.setattr(llm_router, "Router", router)
    llm_router._build_router_from_profiles()
    fallback = router.call_args.kwargs["model_list"][1]["litellm_params"]
    assert fallback["api_key"] == NO_API_KEY


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["api_key", "model", "api_base"])
@pytest.mark.parametrize("operation", ["create", "update", "test"])
async def test_profile_requests_reject_environment_references(field, operation, profile_store):
    body = {field: "os.environ/HBC_SYNTHETIC_KEY"}
    if operation == "create":
        body = {"name": "new", "model": "gpt-5-mini", **body}
    path = "/api/llm/profiles" + ("" if operation == "create" else "/primary")
    if operation == "test":
        path += "/test"
    async with security_client() as (client, _, _):
        response = await client.request("PUT" if operation == "update" else "POST", path, json=body)
    assert response.status_code == 422
    profile_store[1].assert_not_called()
    profile_store[2].assert_not_called()


@pytest.mark.parametrize("field", ["api_key", "model", "api_base"])
def test_provider_boundary_rejects_environment_references(field):
    params = {"model": "gpt-5-mini", "api_key": "synthetic-key", "api_base": "https://provider.test/v1"}
    params[field] = "os.environ/HBC_SYNTHETIC_KEY"
    with pytest.raises(ValueError, match="Environment references"):
        build_llm_params(**params)


def test_keyless_params_do_not_resolve_ambient_openai_key(monkeypatch):
    import litellm

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-ambient-key")
    params = build_llm_params("gpt-5-mini", None, "https://provider.test/v1")
    assert litellm.get_api_key("openai", params["api_key"]) == NO_API_KEY


@pytest.mark.asyncio
async def test_keyless_connection_test_passes_explicit_placeholder(profile_store):
    profile_store[0].llm_profiles[0].api_key = None
    async with security_client() as (client, _, _):
        response = await client.post("/api/llm/profiles/primary/test", json={})
    assert response.status_code == 200
    assert profile_store[2].call_args.kwargs["api_key"] == NO_API_KEY
