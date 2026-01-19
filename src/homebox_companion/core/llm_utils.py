"""LLM credential resolution utilities.

Provides a single source of truth for resolving LLM credentials from:
1. PRIMARY profile from persistent settings
2. Environment variable defaults

This centralizes the resolution logic that was previously duplicated in
ai/llm.py and chat/llm_client.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from . import config
from .persistent_settings import get_primary_profile


@dataclass
class LLMCredentials:
    """Resolved LLM credentials ready for use.

    Attributes:
        model: The model identifier (e.g., 'gpt-5-mini', 'claude-3-opus')
        api_key: The API key for authentication
        api_base: Optional custom API base URL
        profile_name: Name of the profile used, or None if using env defaults
    """

    model: str
    api_key: str | None
    api_base: str | None
    profile_name: str | None = None


def resolve_llm_credentials(
    *,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> LLMCredentials:
    """Resolve LLM credentials using the unified priority order.

    Resolution priority:
    1. Explicit arguments (if provided)
    2. PRIMARY profile from persistent settings
    3. Environment variable defaults

    Args:
        model: Optional explicit model override
        api_key: Optional explicit API key override
        api_base: Optional explicit API base URL override

    Returns:
        LLMCredentials with resolved values
    """
    profile_name: str | None = None

    # Check for PRIMARY profile first
    primary = get_primary_profile()
    if primary:
        profile_name = primary.name
        # Use profile values, allowing explicit overrides
        model = model or primary.model
        api_key = api_key or (primary.api_key.get_secret_value() if primary.api_key else None)
        api_base = api_base if api_base is not None else primary.api_base
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
    )
