"""HTTP-level regression contracts for Homebox authentication modes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

import httpx
import pytest
from pydantic import SecretStr

from homebox_companion.chat.llm_client import LLMClient
from homebox_companion.chat.store import MemorySessionStore
from homebox_companion.core.config import Settings
from homebox_companion.homebox.client import HomeboxClient
from server.app import create_app
from server.dependencies import get_client

UpstreamHandler = Callable[[httpx.Request], httpx.Response]


class _SettingsConstructor(Protocol):
    """Pydantic Settings accepts these runtime-only constructor arguments."""

    def __call__(
        self,
        *,
        _env_file: str | Path | None = ...,
        homebox_api_key: str | SecretStr | None = ...,
        **_kwargs: object,
    ) -> Settings: ...


_settings = cast(_SettingsConstructor, Settings)


@asynccontextmanager
async def _contract_client(app_settings: Settings, handler: UpstreamHandler) -> AsyncIterator[httpx.AsyncClient]:
    """Serve a real app while its Homebox dependency uses an in-memory transport."""
    app = create_app(app_settings)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        homebox = HomeboxClient(base_url=app_settings.api_url, client=upstream)
        app.dependency_overrides[get_client] = lambda: homebox
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://companion.test"
        ) as client:
            yield client


def _user_response(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"item": {"id": "user-1", "defaultGroupId": "group-1"}})


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, "hb_configured"])
async def test_chat_message_and_approval_use_bound_executor(api_key, monkeypatch):
    """Exercise the real dependency chain, mocking only Homebox and the LLM stream."""
    settings = _settings(
        _env_file=None, homebox_api_key=api_key, chat_enabled=True, demo_mode=False, chat_rate_limit_rpm=0
    )
    app = create_app(settings)
    app.state.session_store = MemorySessionStore()
    writes = []

    def upstream(request):
        assert request.headers["Authorization"] == f"Bearer {api_key or 'browser-session'}"
        if request.method == "GET" and request.url.path.endswith("/users/self"):
            return _user_response(request)
        assert request.method == "POST" and request.url.path.endswith("/tags")
        assert request.headers["X-Tenant"] == "selected-group"
        writes.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "tag-1", "name": "Fragile"})

    async def complete_stream(self, messages, tools):
        assert messages[-1]["content"] == "Create a Fragile tag"
        assert any(tool["function"]["name"] == "create_tag" for tool in tools)
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="I'll create that tag.",
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call-create-tag",
                                function=SimpleNamespace(name="create_tag", arguments='{"name":"Fragile"}'),
                            )
                        ],
                    )
                )
            ]
        )

    monkeypatch.setattr("homebox_companion.chat.orchestrator.settings.chat_enabled", True)
    monkeypatch.setattr(LLMClient, "complete_stream", complete_stream)
    monkeypatch.setattr(LLMClient, "get_resolved_model", staticmethod(lambda: "gpt-5-mini"))
    headers = {
        "Authorization": "Bearer browser-session",
        "X-Companion-Request": "1",
        "X-Companion-Chat-Context": "11111111-1111-4111-8111-111111111111",
        "X-Group-Id": "selected-group",
    }
    async with HomeboxClient(base_url=settings.api_url, transport=httpx.MockTransport(upstream)) as homebox:
        app.state.homebox_client = homebox
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://companion.test", headers=headers
        ) as client:
            response = await client.post("/api/chat/messages", json={"message": "Create a Fragile tag"})
            assert response.status_code == 200, response.text
            assert response.headers["content-type"].startswith("text/event-stream")
            assert "event: text" in response.text
            assert "event: approval_required" in response.text
            assert "event: done" in response.text
            assert "event: error" not in response.text
            assert writes == []

            pending = await client.get("/api/chat/pending")
            assert pending.status_code == 200
            (approval,) = pending.json()["approvals"]
            assert approval["tool_name"] == "create_tag"
            approved = await client.post(f"/api/chat/approve/{approval['id']}")
            assert approved.status_code == 200, approved.text
            assert approved.json()["success"] is True
            assert approved.json()["data"]["id"] == "tag-1"
            assert len(writes) == 1 and writes[0]["name"] == "Fragile"

            pending = await client.get("/api/chat/pending")
            assert pending.json()["approvals"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/chat/status", None),
        ("GET", "/api/chat/pending", None),
        ("DELETE", "/api/chat/history", None),
        ("POST", "/api/chat/reject/pending-id", None),
        ("POST", "/api/chat/approve/pending-id", None),
        ("POST", "/api/chat/messages", {"message": "hello"}),
    ],
)
@pytest.mark.parametrize("api_key", [None, "hb_configured"])
async def test_cached_chat_identity_does_not_authorize_revoked_credentials(method, path, body, api_key):
    settings = _settings(_env_file=None, homebox_api_key=api_key, chat_enabled=True, demo_mode=False)
    app = create_app(settings)
    app.state.session_store = MemorySessionStore()
    revoked = False
    requests = []

    def upstream(request):
        requests.append(request)
        assert request.url.path.endswith("/users/self")
        return httpx.Response(401, json={"detail": "revoked"}) if revoked else _user_response(request)

    headers = {
        "Authorization": "Bearer old-session",
        "X-Companion-Request": "1",
        "X-Companion-Chat-Context": "11111111-1111-4111-8111-111111111111",
    }
    async with HomeboxClient(base_url=settings.api_url, transport=httpx.MockTransport(upstream)) as homebox:
        app.state.homebox_client = homebox
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://companion.test", headers=headers
        ) as client:
            initial = await client.get("/api/chat/status")
            assert initial.status_code == 200
            assert app.state.homebox_identities
            revoked = True
            response = await client.request(method, path, json=body)
    assert response.status_code == (502 if api_key else 401)
    assert response.json()["code"] == ("HOMEBOX_API_KEY_REJECTED" if api_key else "AUTH_FAILED")
    assert len(requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("header_token", [None, "different-header-token"])
async def test_legacy_mcp_executes_with_body_token_and_selected_collection(header_token):
    seen = []

    def upstream(request):
        seen.append((request.headers.get("Authorization"), request.headers.get("X-Tenant")))
        return httpx.Response(200, json=[])

    settings = _settings(_env_file=None, homebox_api_key=None, chat_enabled=True)
    headers = {"X-Group-Id": "selected-group"}
    if header_token:
        headers["Authorization"] = f"Bearer {header_token}"
    async with _contract_client(settings, upstream) as client:
        response = await client.post(
            "/api/mcp/v1/tools/list_tags", headers=headers, json={"token": "body-token"}
        )
    assert response.status_code == 200
    assert response.json()["success"]
    assert seen == [("Bearer body-token", "selected-group")]


@pytest.mark.asyncio
async def test_key_mode_mcp_ignores_both_caller_tokens():
    seen = []

    def upstream(request):
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, json=[])

    settings = _settings(_env_file=None, homebox_api_key="hb_configured", chat_enabled=True)
    async with _contract_client(settings, upstream) as client:
        response = await client.post(
            "/api/mcp/v1/tools/list_tags",
            headers={"Authorization": "Bearer header-token", "X-Companion-Request": "1"},
            json={"token": "body-token"},
        )
    assert response.status_code == 200
    assert seen == ["Bearer hb_configured"]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"token": ""}, {"token": 123}, []])
async def test_legacy_mcp_rejects_missing_or_invalid_body_credentials(body):
    seen = []

    def upstream(request):
        seen.append(request)
        return httpx.Response(200, json=[])

    settings = _settings(_env_file=None, homebox_api_key=None, chat_enabled=True)
    async with _contract_client(settings, upstream) as client:
        response = await client.post("/api/mcp/v1/tools/list_tags", json=body)
    assert response.status_code == (400 if isinstance(body, list) else 401)
    assert not seen


@pytest.mark.asyncio
async def test_connection_uses_configured_key_instead_of_browser_bearer() -> None:
    seen_authorization: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_authorization.append(request.headers.get("Authorization"))
        return _user_response(request)

    settings = _settings(_env_file=None, homebox_api_key="hb_server-configured")
    async with _contract_client(settings, handler) as client:
        response = await client.get("/api/homebox/connection", headers={"Authorization": "Bearer stale-browser-token"})

    assert response.status_code == 200
    assert response.json() == {
        "connected": True,
        "context_id": response.json()["context_id"],
        "user_id": "user-1",
        "default_group_id": "group-1",
    }
    assert seen_authorization == ["Bearer hb_server-configured"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("api_key", "request_headers", "status_code", "error_code", "outbound_authorization"),
    [
        pytest.param(
            None,
            {"Authorization": "Bearer legacy-session"},
            401,
            "AUTH_FAILED",
            "Bearer legacy-session",
            id="legacy-session-keeps-401",
        ),
        pytest.param(
            "hb_configured-key",
            {"Authorization": "Bearer stale-session"},
            502,
            "HOMEBOX_API_KEY_REJECTED",
            "Bearer hb_configured-key",
            id="configured-key-translates-401",
        ),
    ],
)
async def test_connection_401_contract_depends_on_auth_mode(
    api_key: str | None,
    request_headers: dict[str, str],
    status_code: int,
    error_code: str,
    outbound_authorization: str,
) -> None:
    seen_authorization: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_authorization.append(request.headers.get("Authorization"))
        return httpx.Response(401, json={"detail": "rejected"})

    async with _contract_client(_settings(_env_file=None, homebox_api_key=api_key), handler) as client:
        response = await client.get("/api/homebox/connection", headers=request_headers)

    assert response.status_code == status_code
    assert response.json()["code"] == error_code
    assert seen_authorization == [outbound_authorization]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "error_code"),
    [
        pytest.param("timeout", "HOMEBOX_TIMEOUT", id="timeout"),
        pytest.param("connect", "HOMEBOX_UNAVAILABLE", id="connect-error"),
    ],
)
async def test_connection_maps_transport_failures_to_safe_503(failure: str, error_code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("slow upstream", request=request)
        raise httpx.ConnectError("offline upstream", request=request)

    async with _contract_client(_settings(_env_file=None, homebox_api_key="hb_configured"), handler) as client:
        response = await client.get("/api/homebox/connection")

    assert response.status_code == 503
    assert response.json()["code"] == error_code


@pytest.mark.asyncio
async def test_connection_preserves_forbidden_and_normalizes_malformed_success() -> None:
    responses = iter(
        [
            httpx.Response(403, json={"detail": "denied"}),
            httpx.Response(200, content=b"not-json", headers={"content-type": "application/json"}),
        ]
    )

    async with _contract_client(
        _settings(_env_file=None, homebox_api_key="hb_configured"), lambda _: next(responses)
    ) as client:
        forbidden = await client.get("/api/homebox/connection")
        malformed = await client.get("/api/homebox/connection")

    assert (forbidden.status_code, forbidden.json()["code"]) == (403, "HOMEBOX_FORBIDDEN")
    assert (malformed.status_code, malformed.json()["code"]) == (502, "HOMEBOX_ERROR")


@pytest.mark.asyncio
async def test_api_key_mode_requires_guard_and_blocks_untrusted_cors_origins() -> None:
    settings = _settings(_env_file=None, homebox_api_key="hb_configured")
    async with _contract_client(settings, _user_response) as client:
        preflight = await client.options(
            "/api/logout",
            headers={
                "Origin": "https://malicious.test",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Companion-Request",
            },
        )
        missing_guard = await client.post("/api/logout")
        cross_origin = await client.post(
            "/api/logout",
            headers={"Origin": "https://malicious.test", "X-Companion-Request": "1"},
        )
        same_origin = await client.post(
            "/api/logout",
            headers={"Origin": "http://companion.test", "X-Companion-Request": "1"},
        )

    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers
    assert (missing_guard.status_code, missing_guard.json()["code"]) == (403, "REQUEST_GUARD_REQUIRED")
    assert (cross_origin.status_code, cross_origin.json()["code"]) == (403, "REQUEST_GUARD_REQUIRED")
    assert same_origin.status_code == 409


@pytest.mark.asyncio
async def test_explicit_api_key_cors_origin_and_legacy_wildcard_remain_usable() -> None:
    request_headers = {
        "Origin": "https://allowed.test",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "X-Companion-Request",
    }
    explicit = _settings(_env_file=None, homebox_api_key="hb_configured", cors_origins="https://allowed.test")
    legacy = _settings(_env_file=None, cors_origins="*")

    async with _contract_client(explicit, _user_response) as client:
        allowed_preflight = await client.options("/api/logout", headers=request_headers)
        allowed_post = await client.post(
            "/api/logout", headers={"Origin": "https://allowed.test", "X-Companion-Request": "1"}
        )
    async with _contract_client(legacy, _user_response) as client:
        legacy_preflight = await client.options("/api/logout", headers=request_headers)

    assert allowed_preflight.status_code == 200
    assert allowed_preflight.headers["access-control-allow-origin"] == "https://allowed.test"
    assert allowed_post.status_code == 409
    assert legacy_preflight.status_code == 200
    assert legacy_preflight.headers["access-control-allow-origin"] == "https://allowed.test"


@pytest.mark.asyncio
async def test_app_instances_and_env_override_keep_auth_configuration_isolated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("HBC_HOMEBOX_API_KEY=hb_dotenv-secret\n", encoding="utf-8")
    with monkeypatch.context() as environment:
        environment.setenv("HBC_HOMEBOX_API_KEY", "hb_environment-secret")
        environment_settings = _settings(_env_file=dotenv)
    assert environment_settings.homebox_api_key is not None
    assert environment_settings.homebox_api_key.get_secret_value() == "hb_environment-secret"

    key_settings = _settings(_env_file=None, homebox_api_key="hb_instance-one")
    legacy_settings = _settings(_env_file=None, homebox_url="https://other-homebox.test")
    async with _contract_client(key_settings, _user_response) as key_client:
        key_config = await key_client.get("/api/config")
        key_connection = await key_client.get("/api/homebox/connection")
    async with _contract_client(legacy_settings, _user_response) as legacy_client:
        legacy_config = await legacy_client.get("/api/config")
        legacy_connection = await legacy_client.get(
            "/api/homebox/connection", headers={"Authorization": "Bearer legacy-session"}
        )

    serialized = environment_settings.model_dump_json()
    assert key_config.json()["auth_mode"] == "api_key"
    assert legacy_config.json()["auth_mode"] == "legacy"
    assert key_connection.json()["context_id"] != legacy_connection.json()["context_id"]
    assert "hb_environment-secret" not in serialized
    assert "hb_instance-one" not in key_config.text + key_connection.text
