"""Focused backend contracts for configured Homebox API-key mode."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Protocol, cast
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import Request
from pydantic import SecretStr

from homebox_companion.chat.orchestrator import ChatOrchestrator
from homebox_companion.core.config import Settings
from homebox_companion.core.exceptions import HomeboxAPIError, HomeboxAuthError, HomeboxConnectionError
from homebox_companion.homebox.auth import (
    ConfiguredAPIKeyProvider,
    HomeboxAccess,
    HomeboxAuthKind,
    LegacySessionProvider,
)
from homebox_companion.homebox.client import HomeboxClient, HomeboxGateway
from homebox_companion.mcp.executor import ToolExecutionContext, ToolExecutor
from server.api.chat import _event_generator
from server.app import create_app
from server.dependencies import (
    get_chat_scope,
    get_client,
    get_executor,
    get_verified_homebox_access,
)


class _SettingsConstructor(Protocol):
    """Runtime Pydantic accepts raw strings before validating SecretStr fields."""

    def __call__(
        self,
        *,
        homebox_api_key: str | SecretStr | None = ...,
        **_kwargs: object,
    ) -> Settings: ...


_settings = cast(_SettingsConstructor, Settings)


def test_blank_key_selects_legacy_and_secret_is_redacted() -> None:
    assert _settings(homebox_api_key="   ").auth_mode == "legacy"
    configured = _settings(homebox_api_key="  hb_secret-value  ")
    assert configured.auth_mode == "api_key"
    assert "secret-value" not in repr(configured)
    assert configured.homebox_api_key is not None
    assert configured.homebox_api_key.get_secret_value() == "hb_secret-value"
    malformed = _settings(homebox_api_key="configured-but-malformed")
    assert malformed.auth_mode == "api_key"


def test_configured_provider_wins_over_browser_bearer_and_preserves_group() -> None:
    configured = _settings(homebox_api_key="hb_configured").homebox_api_key
    assert configured is not None
    access = ConfiguredAPIKeyProvider(configured).resolve("Bearer stale-session", "group-a")
    assert access.credential.get_secret_value() == "hb_configured"
    assert access.group_id == "group-a"
    assert access.identity_scope == "configured-api-key"


def test_legacy_provider_requires_well_formed_bearer() -> None:
    provider = LegacySessionProvider()
    with pytest.raises(ValueError):
        provider.resolve(None)
    assert provider.resolve("Bearer session-a").credential.get_secret_value() == "session-a"


@pytest.mark.asyncio
async def test_config_and_browser_guard_are_mode_aware() -> None:
    app = create_app(_settings(homebox_api_key="hb_configured", cors_origins="https://allowed.test"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://companion.test") as client:
        config = await client.get("/api/config")
        assert config.json()["auth_mode"] == "api_key"

        rejected = await client.post("/api/logout")
        assert rejected.status_code == 403
        assert rejected.json()["code"] == "REQUEST_GUARD_REQUIRED"

        guarded = await client.post("/api/logout", headers={"X-Companion-Request": "1"})
        assert guarded.status_code == 409
        assert guarded.json()["detail"]["code"] == "AUTH_MODE_MISMATCH"


@pytest.mark.asyncio
async def test_mcp_schema_hides_token_in_key_mode() -> None:
    app = create_app(_settings(homebox_api_key="hb_configured"))
    app.dependency_overrides[get_executor] = lambda: ToolExecutor()
    async with HomeboxClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "owner"})),
        allow_cookies=False,
    ) as homebox:
        app.state.homebox_client = homebox
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://companion.test") as client:
            response = await client.get("/api/mcp/v1/tools")
    assert response.status_code == 200
    for tool in response.json()["tools"].values():
        assert "token" not in tool["parameters"].get("properties", {})


@pytest.mark.asyncio
async def test_malformed_key_keeps_key_mode_and_returns_redacted_config_error() -> None:
    secret = "wrong-secret-value"
    app = create_app(_settings(homebox_api_key=secret))
    app.dependency_overrides[get_client] = lambda: HomeboxClient(
        base_url="http://homebox.test/api/v1",
        transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://companion.test") as client:
        config = await client.get("/api/config")
        response = await client.get("/api/homebox/connection")

    assert config.json()["auth_mode"] == "api_key"
    assert response.status_code == 502
    assert response.json()["code"] == "HOMEBOX_API_KEY_INVALID_CONFIG"
    assert secret not in response.text


@pytest.mark.asyncio
async def test_concurrent_gateways_isolate_credentials_and_groups() -> None:
    seen: list[tuple[str | None, str | None, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                request.headers.get("Authorization"),
                request.headers.get("X-Tenant"),
                request.headers.get("Cookie"),
            )
        )
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = HomeboxClient(base_url="http://homebox.test/api/v1", client=transport)
        first = HomeboxGateway(
            client,
            HomeboxAccess(SecretStr("token-a"), HomeboxAuthKind.LEGACY, "user-a", "group-a"),
        )
        second = HomeboxGateway(
            client,
            HomeboxAccess(SecretStr("token-b"), HomeboxAuthKind.LEGACY, "user-b", "group-b"),
        )
        await asyncio.gather(first.list_tags(), second.list_tags())

    assert set(seen) == {
        ("Bearer token-a", "group-a", None),
        ("Bearer token-b", "group-b", None),
    }


@pytest.mark.asyncio
async def test_key_mode_transport_never_sends_cookie_jar() -> None:
    cookies: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cookies.append(request.headers.get("Cookie"))
        return httpx.Response(200, json=[])

    client = HomeboxClient(
        base_url="http://homebox.test/api/v1",
        allow_cookies=False,
        transport=httpx.MockTransport(handler),
    )
    client.client.cookies.set("session", "stale", domain="homebox.test")
    try:
        gateway = HomeboxGateway(
            client,
            HomeboxAccess(SecretStr("hb_key"), HomeboxAuthKind.API_KEY, "user-a"),
        )
        await gateway.list_tags()
    finally:
        await client.aclose()
    assert cookies == [None]


@pytest.mark.asyncio
async def test_entity_type_cache_is_scoped_by_verified_identity_and_group() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        credential = request.headers["Authorization"]
        calls.append(credential)
        suffix = credential.rsplit("-", 1)[-1]
        return httpx.Response(200, json=[{"id": f"type-{suffix}", "isLocation": False}])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = HomeboxClient(base_url="http://homebox.test/api/v1", client=transport)
        first = HomeboxGateway(
            client,
            HomeboxAccess(SecretStr("token-a"), HomeboxAuthKind.LEGACY, "user-a", "group"),
        )
        second = HomeboxGateway(
            client,
            HomeboxAccess(SecretStr("token-b"), HomeboxAuthKind.LEGACY, "user-b", "group"),
        )
        assert await first.transport_client._resolve_entity_type_id("token-a", is_location=False) == "type-a"
        assert await second.transport_client._resolve_entity_type_id("token-b", is_location=False) == "type-b"

    assert calls == ["Bearer token-a", "Bearer token-b"]


def test_gateway_scope_is_immutable() -> None:
    client = HomeboxClient(base_url="http://homebox.test/api/v1")
    gateway = HomeboxGateway(
        client,
        HomeboxAccess(SecretStr("token-a"), HomeboxAuthKind.LEGACY, "user-a", "group-a"),
    )
    with pytest.raises(AttributeError, match="immutable"):
        gateway.access = HomeboxAccess(SecretStr("token-b"), HomeboxAuthKind.LEGACY, "user-b")


@pytest.mark.asyncio
async def test_current_user_unwraps_real_v0262_item_contract_and_rejects_malformed() -> None:
    responses = iter(
        (
            httpx.Response(
                200,
                json={"item": {"id": "user-a", "defaultGroupId": "group-a", "groupIds": ["group-a"]}},
            ),
            httpx.Response(200, json={"item": {"name": "No immutable identity"}}),
        )
    )
    client = HomeboxClient(
        base_url="http://homebox.test/api/v1",
        transport=httpx.MockTransport(lambda _request: next(responses)),
    )
    try:
        assert await client.get_current_user("token") == {
            "id": "user-a",
            "defaultGroupId": "group-a",
            "groupIds": ["group-a"],
        }
        with pytest.raises(HomeboxAPIError, match="User response missing id"):
            await client.get_current_user("token")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_chat_bootstrap_verifies_identity_and_scopes_user_and_effective_group() -> None:
    app_state = SimpleNamespace(
        settings=Settings(),
        homebox_identities={},
    )
    request = SimpleNamespace(app=SimpleNamespace(state=app_state))
    client = AsyncMock()
    client.get_current_user.side_effect = [
        {"id": "same-user", "defaultGroupId": "group-a"},
        {"id": "same-user", "defaultGroupId": "group-a"},
        {"id": "other-user", "defaultGroupId": "group-b"},
    ]

    typed_request = cast(Request, request)
    first = await get_verified_homebox_access(typed_request, "session-before-connection", client, None)
    rotated = await get_verified_homebox_access(typed_request, "refreshed-session", client, None)
    other = await get_verified_homebox_access(typed_request, "other-session", client, None)

    context = "11111111-1111-4111-8111-111111111111"
    assert first.identity_scope == rotated.identity_scope == "same-user"
    assert first.group_id == rotated.group_id == "group-a"
    assert get_chat_scope(typed_request, context, first) == get_chat_scope(typed_request, context, rotated)
    assert get_chat_scope(typed_request, context, first) != get_chat_scope(typed_request, context, other)
    switched = HomeboxAccess(first.credential, first.kind, first.identity_scope, "group-c")
    assert get_chat_scope(typed_request, context, first) != get_chat_scope(typed_request, context, switched)


@pytest.mark.asyncio
async def test_bound_tool_execution_preserves_key_auth_and_network_domain_errors() -> None:
    def rejected(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "credential rejected"})

    rejected_client = HomeboxClient(
        base_url="http://homebox.test/api/v1",
        transport=httpx.MockTransport(rejected),
    )
    rejected_gateway = HomeboxGateway(
        rejected_client,
        HomeboxAccess(SecretStr("hb_key"), HomeboxAuthKind.API_KEY, "user-a"),
    )
    try:
        with pytest.raises(HomeboxAuthError) as auth_error:
            await ToolExecutor().execute(
                "list_tags",
                {},
                context=ToolExecutionContext.for_gateway(rejected_gateway),
            )
        assert auth_error.value.status_code == 502
        assert auth_error.value.error_code == "HOMEBOX_API_KEY_REJECTED"
    finally:
        await rejected_client.aclose()

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private socket detail", request=request)

    network_client = HomeboxClient(
        base_url="http://homebox.test/api/v1",
        transport=httpx.MockTransport(unavailable),
    )
    network_gateway = HomeboxGateway(
        network_client,
        HomeboxAccess(SecretStr("hb_key"), HomeboxAuthKind.API_KEY, "user-a"),
    )
    try:
        with pytest.raises(HomeboxConnectionError):
            await ToolExecutor().execute(
                "list_tags",
                {},
                context=ToolExecutionContext.for_gateway(network_gateway),
            )
    finally:
        await network_client.aclose()


@pytest.mark.asyncio
async def test_sse_domain_error_uses_safe_structured_contract() -> None:
    class FailingOrchestrator:
        async def process_message(self, *_args, **_kwargs):
            if _args is None:
                yield None
            raise HomeboxConnectionError(
                "private socket detail",
                user_message="Homebox is unavailable. Please retry.",
            )

    events = [
        event
        async for event in _event_generator(cast(ChatOrchestrator, FailingOrchestrator()), "hello", "unused")
    ]
    payload = json.loads(events[0]["data"])
    assert payload == {"message": "Homebox is unavailable. Please retry.", "code": "HOMEBOX_UNAVAILABLE"}
    assert "private socket detail" not in events[0]["data"]
