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


# Curated allowlist: keep this small and tested.
# Project policy: prefer GPT-5 models only by default.
MODEL_ALLOWLIST: dict[str, ModelCapabilities] = {
    "gpt-5-mini": ModelCapabilities("gpt-5-mini", vision=True, multi_image=True, json_mode=True),
    "gpt-5-nano": ModelCapabilities("gpt-5-nano", vision=True, multi_image=True, json_mode=True),
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

    caps = MODEL_ALLOWLIST.get(normalized)
    if caps:
        return caps

    if allow_unsafe:
        # Conservative defaults (fail-fast for vision/multi-image; JSON mode off by default).
        return ModelCapabilities(normalized, vision=False, multi_image=False, json_mode=False)

    return None


