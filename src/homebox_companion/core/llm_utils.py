"""LLM credential resolution utilities.

Provides a single source of truth for resolving LLM credentials from:
1. PRIMARY profile from persistent settings
2. Environment variable defaults

This centralizes the resolution logic that was previously duplicated in
ai/llm.py and chat/llm_client.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from loguru import logger

from . import config
from .persistent_settings import get_primary_profile


@dataclass
class LLMCredentials:
    """Resolved LLM credentials ready for use.

    Attributes:
        model: The model identifier (e.g., 'gpt-5.6-luna', 'claude-3-opus')
        api_key: The API key for authentication
        api_base: Optional custom API base URL
        profile_name: Name of the profile used, or None if using env defaults
    """

    model: str
    api_key: str | None
    api_base: str | None
    profile_name: str | None = None
    disable_workers_ai_gemma_thinking: bool = False


def workers_ai_gemma_options(model: str, api_base: str | None, disable_thinking: bool) -> dict[str, Any]:
    """Map the profile option to the Workers AI OpenAI-compatible request."""
    if (
        disable_thinking
        and model == "openai/@cf/google/gemma-4-26b-a4b-it"
        and re.fullmatch(r"https://api\.cloudflare\.com/client/v4/accounts/[0-9a-fA-F]{32}/ai/v1/?", api_base or "")
    ):
        return {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    return {}


def resolve_llm_credentials() -> LLMCredentials:
    """Resolve LLM credentials using the unified priority order.

    Resolution priority:
    1. PRIMARY profile from persistent settings
    2. Environment variable defaults

    Returns:
        LLMCredentials with resolved values
    """
    profile_name: str | None = None
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None

    # Check for PRIMARY profile first
    primary = get_primary_profile()
    if primary:
        profile_name = primary.name
        model = primary.model
        api_key = primary.api_key.get_secret_value() if primary.api_key else None
        api_base = primary.api_base
        logger.debug(f"Using PRIMARY profile '{primary.name}' with model: {model}")
    else:
        logger.debug("No PRIMARY profile, using env defaults")

    # Fall back to env vars for any missing values
    model = model or config.settings.effective_llm_model
    api_key = api_key or config.settings.effective_llm_api_key
    api_base = api_base if api_base is not None else config.settings.llm_api_base

    return LLMCredentials(
        model=model,
        api_key=api_key,
        api_base=api_base,
        profile_name=profile_name,
        disable_workers_ai_gemma_thinking=primary.disable_workers_ai_gemma_thinking if primary else False,
    )
