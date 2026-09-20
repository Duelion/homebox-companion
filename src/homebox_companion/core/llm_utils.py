"""LLM credential resolution utilities.

Provides a single source of truth for resolving LLM credentials from:
1. PRIMARY profile from persistent settings
2. Environment variable defaults

This centralizes the resolution logic that was previously duplicated in
ai/llm.py and chat/llm_client.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import litellm
from loguru import logger

from . import config
from .persistent_settings import get_primary_profile


def same_llm_destination(
    model: str, api_base: str | None, other_model: str, other_api_base: str | None
) -> bool:
    """Permit key reuse only within the same provider and configured endpoint.

    Compare full base paths as well as origins; a proxy may host unrelated
    providers under different paths. Unknown provider changes fail closed.
    """
    if (api_base or "").rstrip("/") != (other_api_base or "").rstrip("/"):
        return False
    if model == other_model:
        return True
    try:
        # A placeholder prevents provider discovery from resolving credentials.
        _, provider, _, resolved_base = litellm.get_llm_provider(
            model=model, api_base=api_base, api_key="destination-check"
        )
        _, other_provider, _, other_resolved_base = litellm.get_llm_provider(
            model=other_model, api_base=other_api_base, api_key="destination-check"
        )
    except Exception:
        return False
    return provider == other_provider and resolved_base == other_resolved_base


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
    api_base = api_base if api_base is not None else config.settings.llm_api_base
    if not api_key and same_llm_destination(
        model, api_base, config.settings.effective_llm_model, config.settings.llm_api_base
    ):
        api_key = config.settings.effective_llm_api_key

    return LLMCredentials(
        model=model,
        api_key=api_key,
        api_base=api_base,
        profile_name=profile_name,
    )
