"""Homebox log authorization and forward-only credential redaction."""

from __future__ import annotations

import io
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from loguru import logger

from homebox_companion.core import logging as app_logging
from homebox_companion.core.config import Settings
from homebox_companion.core.exceptions import LLMServiceError
from homebox_companion.core.redaction import redact_sensitive, register_secrets
from homebox_companion.homebox.client import HomeboxClient
from server.api import logs
from server.app import create_app

_PATHS = ("/api/logs", "/api/logs/download", "/api/logs/llm-debug", "/api/logs/llm-debug/download")


@asynccontextmanager
async def client_for(*, upstream_status=200, api_key=None):
    settings = Settings(_env_file=None, homebox_api_key=api_key)
    app = create_app(settings)
    async with HomeboxClient(
        base_url="http://homebox.test/api/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(upstream_status, json={"id": "member"})),
        allow_cookies=False,
    ) as homebox:
        app.state.homebox_client = homebox
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://companion.test",
            headers={"Authorization": "Bearer session"},
        ) as client:
            yield client


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("api_key,expected", [(None, 401), ("hb_synthetic-key", 502)])
async def test_log_routes_revalidate_revoked_homebox(path, api_key, expected):
    async with client_for(upstream_status=401, api_key=api_key) as client:
        response = await client.get(path)
    assert response.status_code == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("date", [None, "2026-10-23"])
@pytest.mark.parametrize("api_key", [None, "hb_synthetic-key"])
async def test_historical_logs_remain_unchanged_and_homebox_readable(path, date, api_key, monkeypatch, tmp_path):
    monkeypatch.setattr(logs, "_LOGS_DIR", str(tmp_path))
    original = b'{"historical": "synthetic-old-key", "api_key": "kept-exactly"}\n'
    paths = [tmp_path / f"{prefix}2026-10-23.log" for prefix in ("homebox_companion_", "llm_debug_")]
    for log_path in paths:
        log_path.write_bytes(original)
    async with client_for(api_key=api_key) as client:
        response = await client.get(path, params={"date": date} if date else {})
    assert response.status_code == 200
    if path.endswith("download"):
        assert response.content == original
    else:
        assert response.json()["logs"].encode() == original
    assert all(log_path.read_bytes() == original for log_path in paths)


@pytest.mark.parametrize("secret", ["q7!x", "synthetic-" + "long-key-value-" * 30])
def test_redacts_full_and_truncated_configured_values(secret):
    register_secrets(secret)
    assert secret not in redact_sensitive(f"error {secret}")
    if len(secret) > 112:
        assert secret[:8] not in redact_sensitive(f"error {secret[:112]}...")


def test_redacts_quoted_credentials_and_preserves_jsonl():
    entry = {"password": 'secret with "quote"', "content": 'api_key="unknown-key" password=other'}
    result = redact_sensitive(json.dumps(entry) + "\n")
    parsed = json.loads(result)
    assert parsed["password"] == "[REDACTED]"
    assert "unknown-key" not in parsed["content"]
    assert "other" not in parsed["content"]
    assert result.endswith("\n")


def test_short_configured_secret_cannot_hide_other_credential_labels():
    register_secrets("key")
    result = redact_sensitive('api_key="unregistered-credential" Authorization: Bearer z9V2mN8-unknown')
    assert "unregistered-credential" not in result
    assert "z9V2mN8-unknown" not in result


def test_overlapping_configured_prefixes_consume_the_entire_matching_fragment():
    first = "p4zM8tV2-" + "first-key-material" * 20
    second = "p4zM8tV2-" + "second-key-material" * 10
    register_secrets(first, second)
    assert redact_sensitive(second) == "[REDACTED]"
    assert redact_sensitive(second[:112]) == "[REDACTED]"


def test_sinks_disable_diagnostic_locals_and_redact_exception_chains(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    output = io.StringIO()
    monkeypatch.setattr(app_logging.sys, "stderr", output)
    key = "z8vQ2mR9-synthetic-" + "longvalue" * 30
    register_secrets(key)
    app_logging.setup_logging()
    try:

        def fail():
            private_local = "PRIVATE-LOCAL-SENTINEL"
            try:
                raise ValueError(key[:112])
            except ValueError as cause:
                raise RuntimeError("Authorization: Bearer synthetic-credential") from cause
            return private_local

        try:
            fail()
        except RuntimeError:
            logger.exception("forced failure")
        logger.bind(llm_debug=True).info(json.dumps({"api_key": key, "request_id": "llm-123"}))
    finally:
        logger.remove()
        logger.configure(patcher=None)
    emitted = output.getvalue() + "".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "logs").glob("*.log")
    )
    assert "PRIVATE-LOCAL-SENTINEL" not in emitted
    assert key[:8] not in emitted
    assert "synthetic-credential" not in emitted
    assert "forced failure" in emitted
    assert "ValueError" in emitted
    llm_path = next((tmp_path / "logs").glob("llm_debug_*.log"))
    assert json.loads(llm_path.read_text(encoding="utf-8"))["request_id"] == "llm-123"


@pytest.mark.asyncio
async def test_provider_failure_has_safe_domain_error(monkeypatch, tmp_path):
    # Import the module rather than the public completion function.
    import importlib

    module = importlib.import_module("homebox_companion.ai.json_completion")
    secret = "provider-failure-sentinel-" + "secretvalue" * 20
    completion = AsyncMock(side_effect=RuntimeError(secret))
    monkeypatch.setattr(module, "get_router", lambda: SimpleNamespace(acompletion=completion))
    monkeypatch.setattr(module, "is_rate_limiting_enabled", lambda: False)
    with pytest.raises(LLMServiceError) as caught:
        await module.json_completion([{"role": "user", "content": "test"}])
    assert secret not in str(caught.value)
    assert "provider request failed" in str(caught.value)
    assert caught.value.user_message == str(caught.value)

    app = create_app(Settings(_env_file=None), static_directory=str(tmp_path / "absent-static"))

    @app.get("/api/test-provider-failure")
    async def forced_failure():
        await module.json_completion([{"role": "user", "content": "test"}])

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://companion.test") as client:
        response = await client.get("/api/test-provider-failure", headers={"X-Request-ID": "safe-correlation-123"})
    assert response.status_code == 502
    assert response.json()["code"] == "LLM_UNAVAILABLE"
    assert response.headers["X-Request-ID"] == "safe-correlation-123"
    assert "provider request failed" in response.json()["detail"]
    assert secret not in response.text
