"""Shared detail policy for dedicated LLM interaction JSONL records."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from .logging import get_log_level_value


def _without_images(value: Any) -> Any:
    """Keep text context while excluding image URLs and base64 payloads."""
    if isinstance(value, list):
        return [_without_images(item) for item in value]
    if isinstance(value, dict):
        if value.get("type") in {"image_url", "image", "input_image"}:
            return {"type": value["type"], "omitted": True}
        return {key: _without_images(item) for key, item in value.items()}
    if isinstance(value, str):
        return re.sub(r"data:image/[^;\s]+;base64,[A-Za-z0-9+/=_-]+", "[image payload omitted]", value)
    return value


def _build_log_entry(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    response_content: str,
    response_tool_calls: list[dict[str, Any]] | None,
    latency_ms: int,
    model: str,
) -> dict[str, Any]:
    """Build a log entry with detail level based on configured log level.

    Detail levels:
    - TRACE: Full detail (all messages, complete tool schemas, full response)
    - DEBUG: Moderate detail (all messages, tool names only, full response)
    - INFO+: Minimal (timestamp, model, latency, counts/summaries)

    Args:
        messages: The messages sent to the LLM.
        tools: The tool definitions sent to the LLM.
        response_content: The response content from the LLM.
        response_tool_calls: The tool calls from the response.
        latency_ms: Time taken for the request in milliseconds.
        model: The model identifier used for this request.

    Returns:
        Dict containing the log entry with appropriate detail level.
    """
    level_value = get_log_level_value()
    timestamp = datetime.now(UTC).isoformat()

    # Base entry (always included)
    entry: dict[str, Any] = {
        "timestamp": timestamp,
        "latency_ms": latency_ms,
        "model": model,
    }

    if level_value <= logger.level("TRACE").no:
        # TRACE: Full detail
        entry["request"] = {
            "messages": _without_images(messages),
            "tools": tools,
        }
        entry["response"] = {
            "content": response_content,
            "tool_calls": response_tool_calls,
        }
    elif level_value <= logger.level("DEBUG").no:
        # DEBUG: Moderate detail - tool names only, no full schemas
        entry["request"] = {
            "messages": _without_images(messages),
            "tool_names": [t["function"]["name"] for t in tools] if tools else None,
        }
        entry["response"] = {
            "content": response_content,
            "tool_calls": response_tool_calls,
        }
    else:
        # INFO+: Minimal - just summaries
        entry["request"] = {
            "message_count": len(messages),
            "tool_count": len(tools) if tools else 0,
            "tool_names": [t["function"]["name"] for t in tools] if tools else None,
        }
        entry["response"] = {
            "content_length": len(response_content),
            "tool_call_count": len(response_tool_calls) if response_tool_calls else 0,
            "tool_calls_summary": ([tc.get("name") for tc in response_tool_calls] if response_tool_calls else None),
        }

    return entry


def log_interaction(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    response_content: str,
    response_tool_calls: list[dict[str, Any]] | None,
    latency_ms: int,
    model: str,
    *,
    interaction: str | None = None,
    error_type: str | None = None,
) -> None:
    """Log chat or vision interactions to the existing dedicated JSONL sink.

    Image payloads are omitted before emission. Credential redaction remains
    the responsibility of the central logging patcher.

    The detail level varies based on the configured log level:
    - TRACE: Full messages, full tool schemas, full response
    - DEBUG: Full messages, tool names only, full response
    - INFO+: Counts and summaries only

    Args:
        messages: The exact messages sent to the LLM.
        tools: The tool definitions sent to the LLM.
        response_content: The accumulated response content.
        response_tool_calls: The parsed tool calls from the response.
        latency_ms: Time taken for the request in milliseconds.
        model: The model identifier used for this request.
        interaction: Optional operation identifier, such as vision_repair.
        error_type: Exception class name only; never a provider exception message.
    """
    try:
        entry = _build_log_entry(messages, tools, response_content, response_tool_calls, latency_ms, model)

        if interaction is not None:
            entry["interaction"] = interaction
        if error_type is not None:
            entry["error_type"] = error_type

        # Log with llm_debug=True so it's captured by the dedicated handler
        logger.bind(llm_debug=True).info(json.dumps(_without_images(entry)))
        logger.trace("[LLM_LOG] Logged interaction")

    except Exception as e:
        logger.warning("[LLM_LOG] Failed to log interaction ({})", type(e).__name__)
