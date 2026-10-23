"""Dedicated vision logs share chat detail and central redaction policies."""

import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from loguru import logger

from homebox_companion.core import llm_logging
from homebox_companion.core.exceptions import JSONRepairError, LLMServiceError


@pytest.mark.asyncio
@pytest.mark.parametrize("level,has_content", [(20, False), (10, True), (5, True)])
async def test_vision_completion_and_repair_are_logged_without_images(monkeypatch, level, has_content):
    module = importlib.import_module("homebox_companion.ai.json_completion")
    responses = ["broken", '{"items": []}']
    router = SimpleNamespace(
        acompletion=AsyncMock(
            side_effect=[
                SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=value))], usage=None)
                for value in responses
            ]
        )
    )
    monkeypatch.setattr(module, "get_router", lambda: router)
    monkeypatch.setattr(module, "is_rate_limiting_enabled", lambda: False)
    monkeypatch.setattr(llm_logging, "get_log_level_value", lambda: level)
    records = []
    sink = logger.add(
        lambda message: records.append(json.loads(str(message))),
        filter=lambda record: record["extra"].get("llm_debug", False),
        format="{message}",
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Identify this"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,IMAGE_SENTINEL"}},
                {"type": "image_url", "image_url": {"url": "https://image.invalid/private"}},
            ],
        }
    ]
    try:
        assert await module.json_completion(messages, expected_keys=["items"]) == {"items": []}
    finally:
        logger.remove(sink)
    assert [record["interaction"] for record in records] == ["vision_completion", "vision_repair"]
    assert all(("messages" in record["request"]) == has_content for record in records)
    assert all(("content" in record["response"]) == has_content for record in records)
    assert "IMAGE_SENTINEL" not in json.dumps(records)
    assert "image.invalid" not in json.dumps(records)
    assert "IMAGE_SENTINEL" in json.dumps(messages)  # Never mutate the provider request.


@pytest.mark.asyncio
@pytest.mark.parametrize("repair", [False, True])
async def test_vision_failures_log_only_exception_type(monkeypatch, repair):
    module = importlib.import_module("homebox_companion.ai.json_completion")
    failure = RuntimeError("PRIVATE_PROVIDER_CREDENTIAL_SENTINEL")
    responses = [failure]
    if repair:
        responses.insert(
            0, SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="broken"))], usage=None)
        )
    monkeypatch.setattr(module, "get_router", lambda: SimpleNamespace(acompletion=AsyncMock(side_effect=responses)))
    monkeypatch.setattr(module, "is_rate_limiting_enabled", lambda: False)
    records = []
    monkeypatch.setattr(module, "log_interaction", lambda *args, **kwargs: records.append(kwargs))
    with pytest.raises(JSONRepairError if repair else LLMServiceError):
        await module.json_completion([{"role": "user", "content": "test"}])
    assert records[-1]["error_type"] == "RuntimeError"
    assert records[-1]["interaction"] == ("vision_repair" if repair else "vision_completion")
    assert "PRIVATE_PROVIDER" not in json.dumps(records)


def test_nested_image_data_urls_are_removed_without_mutation():
    entry = {
        "response": {"content": "Image: data:image/png;base64,SECRET_IMAGE== rest"},
        "nested": ["data:image/jpeg;base64,SECOND_PAYLOAD"],
    }
    sanitized = llm_logging._without_images(entry)
    assert "SECRET_IMAGE" not in json.dumps(sanitized)
    assert "SECOND_PAYLOAD" not in json.dumps(sanitized)
    assert sanitized["response"]["content"].endswith(" rest")
    assert "SECRET_IMAGE" in json.dumps(entry)


@pytest.mark.asyncio
async def test_vision_reaches_dedicated_jsonl_sink_with_central_redaction(monkeypatch, tmp_path):
    import io

    from homebox_companion.core import logging as app_logging
    from homebox_companion.core.redaction import register_secrets

    module = importlib.import_module("homebox_companion.ai.json_completion")
    synthetic_secret = "vision-log-synthetic-credential-63819"
    register_secrets(synthetic_secret)
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"items": []}'))], usage=None)
    monkeypatch.setattr(module, "get_router", lambda: SimpleNamespace(acompletion=AsyncMock(return_value=response)))
    monkeypatch.setattr(module, "is_rate_limiting_enabled", lambda: False)
    monkeypatch.setattr(llm_logging, "get_log_level_value", lambda: 10)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_logging.sys, "stderr", io.StringIO())
    app_logging.setup_logging()
    try:
        await module.json_completion([{"role": "user", "content": synthetic_secret}])
    finally:
        logger.remove()
        logger.configure(patcher=None)
    path = next((tmp_path / "logs").glob("llm_debug_*.log"))
    content = path.read_text(encoding="utf-8")
    assert synthetic_secret not in content
    record = json.loads(content)
    assert record["interaction"] == "vision_completion"
    assert "[REDACTED]" in record["request"]["messages"][0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_model,hidden_model,expected",
    [
        ("gpt-5.6-luna", "primary", "gpt-5.6-luna"),
        ("", "provider-fallback-model", "provider-fallback-model"),
        (None, None, "primary"),
    ],
)
async def test_vision_logs_provider_model_before_router_alias(monkeypatch, response_model, hidden_model, expected):
    module = importlib.import_module("homebox_companion.ai.json_completion")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"items": []}'))],
        model=response_model,
        _hidden_params={"model": hidden_model},
    )
    router = SimpleNamespace(acompletion=AsyncMock(return_value=response))
    records = []
    monkeypatch.setattr(module, "log_interaction", lambda *args, **kwargs: records.append(args))
    for interaction in ("vision_completion", "vision_repair"):
        assert await module._logged_completion(router, {"model": "primary", "messages": []}, interaction) is response
    assert [record[5] for record in records] == [expected, expected]
