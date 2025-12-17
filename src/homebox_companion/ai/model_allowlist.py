"""Curated model allowlist + deterministic capability metadata.

The allowlist is authoritative: we do not attempt runtime capability discovery in production.
This keeps behavior predictable and enables fail-fast errors for unsupported flows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCapabilities:
    """Capabilities for an allowlisted model."""

    model: str
    vision: bool = False
    multi_image: bool = False
    json_mode: bool = False


def extract_base_model(model: str) -> str:
    """Extract canonical base model name from provider-prefixed string.

    Examples:
      - "gpt-5-mini" -> "gpt-5-mini"
      - "openrouter/openai/gpt-5-mini" -> "gpt-5-mini"
      - "openrouter/anthropic/claude-3.5-sonnet" -> "claude-3.5-sonnet"
      - "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0" -> "claude-3-5-sonnet-20241022-v2:0"

    Notes:
      - We intentionally keep this parsing conservative and deterministic.
      - Capability lookup is based on the last path segment (after the final "/").
      - We do not attempt to normalize model versions beyond basic prefix stripping.
    """

    normalized = (model or "").strip()
    if not normalized:
        return ""

    # Prefer last path segment for provider-prefixed models (e.g. openrouter/openai/gpt-5-mini)
    base = normalized.rsplit("/", 1)[-1]

    # Handle formats like "anthropic.claude-3-5-sonnet-..." by dropping the leading provider
    # segment.
    # (Common with Bedrock / Vertex naming conventions.)
    provider_prefixes = ("anthropic", "meta", "amazon", "cohere")
    if "." in base:
        first, rest = base.split(".", 1)
        if first in provider_prefixes and rest:
            base = rest

    return base


# Curated allowlist: keep this small and tested.
# Project policy: prefer GPT-5 models only by default.
MODEL_ALLOWLIST: dict[str, ModelCapabilities] = {
    "anthropic.claude-3-5-sonnet-20240620-v1:0": ModelCapabilities("anthropic.claude-3-5-sonnet-20240620-v1:0", vision=True, multi_image=True, json_mode=True),
    "anthropic.claude-3-5-sonnet-20241022-v2:0": ModelCapabilities("anthropic.claude-3-5-sonnet-20241022-v2:0", vision=True, multi_image=True, json_mode=True),
    "anthropic.claude-3-7-sonnet-20240620-v1:0": ModelCapabilities("anthropic.claude-3-7-sonnet-20240620-v1:0", vision=True, multi_image=True, json_mode=True),
    "anthropic.claude-3-haiku-20240307-v1:0": ModelCapabilities("anthropic.claude-3-haiku-20240307-v1:0", vision=True, multi_image=True, json_mode=True),
    "anthropic.claude-3-opus-20240229-v1:0": ModelCapabilities("anthropic.claude-3-opus-20240229-v1:0", vision=True, multi_image=True, json_mode=True),
    "anthropic.claude-3-sonnet-20240229-v1:0": ModelCapabilities("anthropic.claude-3-sonnet-20240229-v1:0", vision=True, multi_image=True, json_mode=True),
    "apac.anthropic.claude-3-5-sonnet-20240620-v1:0": ModelCapabilities("apac.anthropic.claude-3-5-sonnet-20240620-v1:0", vision=True, multi_image=True, json_mode=True),
    "apac.anthropic.claude-3-5-sonnet-20241022-v2:0": ModelCapabilities("apac.anthropic.claude-3-5-sonnet-20241022-v2:0", vision=True, multi_image=True, json_mode=True),
    "apac.anthropic.claude-3-haiku-20240307-v1:0": ModelCapabilities("apac.anthropic.claude-3-haiku-20240307-v1:0", vision=True, multi_image=True, json_mode=True),
    "apac.anthropic.claude-3-sonnet-20240229-v1:0": ModelCapabilities("apac.anthropic.claude-3-sonnet-20240229-v1:0", vision=True, multi_image=True, json_mode=True),
    "azure/codex-mini": ModelCapabilities("azure/codex-mini", vision=True, multi_image=True, json_mode=True),
    "azure/computer-use-preview": ModelCapabilities("azure/computer-use-preview", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-4o-2024-08-06": ModelCapabilities("azure/eu/gpt-4o-2024-08-06", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-4o-2024-11-20": ModelCapabilities("azure/eu/gpt-4o-2024-11-20", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-4o-mini-2024-07-18": ModelCapabilities("azure/eu/gpt-4o-mini-2024-07-18", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-5-2025-08-07": ModelCapabilities("azure/eu/gpt-5-2025-08-07", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-5-mini-2025-08-07": ModelCapabilities("azure/eu/gpt-5-mini-2025-08-07", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-5-nano-2025-08-07": ModelCapabilities("azure/eu/gpt-5-nano-2025-08-07", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-5.1": ModelCapabilities("azure/eu/gpt-5.1", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-5.1-chat": ModelCapabilities("azure/eu/gpt-5.1-chat", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-5.1-codex": ModelCapabilities("azure/eu/gpt-5.1-codex", vision=True, multi_image=True, json_mode=True),
    "azure/eu/gpt-5.1-codex-mini": ModelCapabilities("azure/eu/gpt-5.1-codex-mini", vision=True, multi_image=True, json_mode=True),
    "azure/global-standard/gpt-4o-2024-08-06": ModelCapabilities("azure/global-standard/gpt-4o-2024-08-06", vision=True, multi_image=True, json_mode=True),
    "azure/global-standard/gpt-4o-2024-11-20": ModelCapabilities("azure/global-standard/gpt-4o-2024-11-20", vision=True, multi_image=True, json_mode=True),
    "azure/global-standard/gpt-4o-mini": ModelCapabilities("azure/global-standard/gpt-4o-mini", vision=True, multi_image=True, json_mode=True),
    "azure_ai/claude-haiku-4-5": ModelCapabilities("azure_ai/claude-haiku-4-5", vision=True, multi_image=True, json_mode=True),
    "azure_ai/claude-opus-4-1": ModelCapabilities("azure_ai/claude-opus-4-1", vision=True, multi_image=True, json_mode=True),
    "azure_ai/claude-sonnet-4-5": ModelCapabilities("azure_ai/claude-sonnet-4-5", vision=True, multi_image=True, json_mode=True),
    "claude-3-5-haiku-20241022": ModelCapabilities("claude-3-5-haiku-20241022", vision=True, multi_image=True, json_mode=True),
    "claude-3-5-haiku-latest": ModelCapabilities("claude-3-5-haiku-latest", vision=True, multi_image=True, json_mode=True),
    "claude-3-5-sonnet-20240620": ModelCapabilities("claude-3-5-sonnet-20240620", vision=True, multi_image=True, json_mode=True),
    "claude-3-5-sonnet-20241022": ModelCapabilities("claude-3-5-sonnet-20241022", vision=True, multi_image=True, json_mode=True),
    "claude-3-5-sonnet-latest": ModelCapabilities("claude-3-5-sonnet-latest", vision=True, multi_image=True, json_mode=True),
    "claude-3-7-sonnet-20250219": ModelCapabilities("claude-3-7-sonnet-20250219", vision=True, multi_image=True, json_mode=True),
    "claude-3-7-sonnet-latest": ModelCapabilities("claude-3-7-sonnet-latest", vision=True, multi_image=True, json_mode=True),
    "claude-3-haiku-20240307": ModelCapabilities("claude-3-haiku-20240307", vision=True, multi_image=True, json_mode=True),
    "claude-3-opus-20240229": ModelCapabilities("claude-3-opus-20240229", vision=True, multi_image=True, json_mode=True),
    "codex-mini-latest": ModelCapabilities("codex-mini-latest", vision=True, multi_image=True, json_mode=True),
    "eu.anthropic.claude-3-5-sonnet-20240620-v1:0": ModelCapabilities("eu.anthropic.claude-3-5-sonnet-20240620-v1:0", vision=True, multi_image=True, json_mode=True),
    "eu.anthropic.claude-3-5-sonnet-20241022-v2:0": ModelCapabilities("eu.anthropic.claude-3-5-sonnet-20241022-v2:0", vision=True, multi_image=True, json_mode=True),
    "eu.anthropic.claude-3-7-sonnet-20250219-v1:0": ModelCapabilities("eu.anthropic.claude-3-7-sonnet-20250219-v1:0", vision=True, multi_image=True, json_mode=True),
    "eu.anthropic.claude-3-haiku-20240307-v1:0": ModelCapabilities("eu.anthropic.claude-3-haiku-20240307-v1:0", vision=True, multi_image=True, json_mode=True),
    "eu.anthropic.claude-3-opus-20240229-v1:0": ModelCapabilities("eu.anthropic.claude-3-opus-20240229-v1:0", vision=True, multi_image=True, json_mode=True),
    "eu.anthropic.claude-3-sonnet-20240229-v1:0": ModelCapabilities("eu.anthropic.claude-3-sonnet-20240229-v1:0", vision=True, multi_image=True, json_mode=True),
    "gemini-1.5-flash": ModelCapabilities("gemini-1.5-flash", vision=True, multi_image=True, json_mode=True),
    "gemini-1.5-flash-001": ModelCapabilities("gemini-1.5-flash-001", vision=True, multi_image=True, json_mode=True),
    "gemini-1.5-flash-002": ModelCapabilities("gemini-1.5-flash-002", vision=True, multi_image=True, json_mode=True),
    "gemini-1.5-flash-exp-0827": ModelCapabilities("gemini-1.5-flash-exp-0827", vision=True, multi_image=True, json_mode=True),
    "gemini-1.5-pro": ModelCapabilities("gemini-1.5-pro", vision=True, multi_image=True, json_mode=True),
    "gemini-1.5-pro-001": ModelCapabilities("gemini-1.5-pro-001", vision=True, multi_image=True, json_mode=True),
    "gemini-1.5-pro-002": ModelCapabilities("gemini-1.5-pro-002", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash": ModelCapabilities("gemini-2.0-flash", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash-001": ModelCapabilities("gemini-2.0-flash-001", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash-exp": ModelCapabilities("gemini-2.0-flash-exp", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash-lite": ModelCapabilities("gemini-2.0-flash-lite", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash-lite-001": ModelCapabilities("gemini-2.0-flash-lite-001", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash-live-preview-04-09": ModelCapabilities("gemini-2.0-flash-live-preview-04-09", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash-preview-image-generation": ModelCapabilities("gemini-2.0-flash-preview-image-generation", vision=True, multi_image=True, json_mode=True),
    "gemini-2.0-flash-thinking-exp": ModelCapabilities("gemini-2.0-flash-thinking-exp", vision=True, multi_image=True, json_mode=True),
    "gpt-5-mini": ModelCapabilities("gpt-5-mini", vision=True, multi_image=True, json_mode=True),
    "gpt-5-nano": ModelCapabilities("gpt-5-nano", vision=True, multi_image=True, json_mode=True),
    "o1": ModelCapabilities("o1", vision=True, multi_image=True, json_mode=True),
    "xai/grok-4-1-fast": ModelCapabilities("xai/grok-4-1-fast", vision=True, multi_image=True, json_mode=True),
    "xai/grok-4-1-fast-non-reasoning": ModelCapabilities("xai/grok-4-1-fast-non-reasoning", vision=True, multi_image=True, json_mode=True),
    "xai/grok-4-1-fast-non-reasoning-latest": ModelCapabilities("xai/grok-4-1-fast-non-reasoning-latest", vision=True, multi_image=True, json_mode=True),
    "xai/grok-4-1-fast-reasoning": ModelCapabilities("xai/grok-4-1-fast-reasoning", vision=True, multi_image=True, json_mode=True),
    "xai/grok-4-1-fast-reasoning-latest": ModelCapabilities("xai/grok-4-1-fast-reasoning-latest", vision=True, multi_image=True, json_mode=True),
}


def get_model_capabilities(
    model: str | None, *, allow_unsafe: bool = False
) -> ModelCapabilities | None:
    """Return capabilities for the given model name.

    Args:
        model: User-provided model identifier (e.g. "gpt-5-mini").
        allow_unsafe: If true, allow unknown models with conservative capabilities.

    Returns:
        Capabilities for allowlisted models, conservative defaults for unknown models
        when unsafe is enabled, otherwise None.
    """

    normalized = (model or "").strip()
    if not normalized:
        return None

    base_model = extract_base_model(normalized)

    caps = MODEL_ALLOWLIST.get(base_model)
    if caps:
        return caps

    if allow_unsafe:
        # Conservative defaults (fail-fast for vision/multi-image; JSON mode off by default).
        return ModelCapabilities(normalized, vision=False, multi_image=False, json_mode=False)

    return None

