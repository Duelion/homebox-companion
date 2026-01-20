"""LiteLLM Router singleton for unified LLM access with automatic fallback.

This module provides a centralized Router that:
- Syncs with ModelProfile settings (PRIMARY/FALLBACK)
- Handles retries with exponential backoff
- Manages cooldowns for failed deployments
- Provides a single entry point for all LLM completions

Usage:
    from homebox_companion.core.llm_router import get_router

    router = get_router()
    response = await router.acompletion(model="primary", messages=[...])
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import litellm
from litellm.integrations.custom_logger import CustomLogger
from litellm.router import Router
from loguru import logger

from .persistent_settings import get_fallback_profile

if TYPE_CHECKING:
    from .persistent_settings import ModelProfile


class FallbackLogger(CustomLogger):
    """Custom logger to track fallback events.

    Logs a warning when a primary deployment fails and fallback is triggered.
    This provides visibility into LLM reliability issues.
    """

    def log_failure_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Log when an LLM call fails (may trigger fallback)."""
        model = kwargs.get("model", "unknown")
        exception = kwargs.get("exception", "Unknown error")
        logger.warning(f"LLM call failed for model '{model}': {exception}")

    async def async_log_failure_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Async version - log when an LLM call fails."""
        model = kwargs.get("model", "unknown")
        exception = kwargs.get("exception", "Unknown error")
        logger.warning(f"LLM call failed for model '{model}': {exception}")

    def log_success_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Log successful LLM calls at debug level."""
        model = kwargs.get("model", "unknown")
        logger.debug(f"LLM call to '{model}' succeeded")

    async def async_log_success_event(
        self,
        kwargs: dict,
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Async version - log successful LLM calls."""
        model = kwargs.get("model", "unknown")
        logger.debug(f"LLM call to '{model}' succeeded")


# Singleton logger instance
_fallback_logger = FallbackLogger()

# Module-level singleton
_router: Router | None = None

# Constant for primary model name used in Router configuration
PRIMARY_MODEL_NAME = "primary"

# Public API
__all__ = [
    "get_router",
    "invalidate_router",
    "get_primary_model_name",
    "PRIMARY_MODEL_NAME",
]


def get_router() -> Router:
    """Get or create the LiteLLM Router singleton.

    The Router is built lazily on first access using current profile settings.
    Call invalidate_router() when profiles change to trigger a rebuild.

    Returns:
        Configured Router instance.

    Raises:
        ValueError: If no PRIMARY profile or env defaults are available.
    """
    global _router
    if _router is None:
        _router = _build_router_from_profiles()
    return _router


def invalidate_router() -> None:
    """Clear the Router singleton to force rebuild on next access.

    Call this when:
    - LLM profiles are added, removed, or modified
    - PRIMARY/FALLBACK status changes
    """
    global _router
    if _router is not None:
        logger.debug("Invalidating LLM Router - will rebuild on next access")
    _router = None


def get_primary_model_name() -> str:
    """Get the Router model_name for the primary deployment.

    This is the key callers should use when calling router.acompletion().

    Returns:
        "primary" - the model_name used in Router configuration.

    Note:
        This function returns PRIMARY_MODEL_NAME constant. It exists for
        backward compatibility and semantic clarity at call sites.
    """
    return PRIMARY_MODEL_NAME


def _build_router_from_profiles() -> Router:
    """Build Router from current PRIMARY and FALLBACK profiles.

    The Router's model_list is constructed with:
    - "primary" deployment from PRIMARY profile (or env defaults)
    - "fallback" deployment from FALLBACK profile (if configured)

    Returns:
        Configured Router with retry and cooldown settings.
    """
    from .llm_utils import resolve_llm_credentials

    # Register our fallback logger with litellm (idempotent check)
    if _fallback_logger not in litellm.callbacks:
        litellm.callbacks.append(_fallback_logger)
        logger.debug("Registered FallbackLogger with LiteLLM")

    model_list: list[dict[str, Any]] = []

    # Build primary deployment from resolved credentials
    primary_creds = resolve_llm_credentials()

    if not primary_creds.model:
        raise ValueError(
            "No LLM model configured. Set HBC_LLM_MODEL environment variable "
            "or configure a PRIMARY LLM profile in Settings."
        )

    primary_params: dict[str, Any] = {
        "model": primary_creds.model,
    }
    if primary_creds.api_key:
        primary_params["api_key"] = primary_creds.api_key
    if primary_creds.api_base:
        primary_params["api_base"] = primary_creds.api_base

    model_list.append({
        "model_name": "primary",
        "litellm_params": primary_params,
    })

    logger.debug(
        f"Router primary deployment: model={primary_creds.model}, "
        f"profile={primary_creds.profile_name or 'env'}"
    )

    # Add fallback deployment if configured
    fallback = get_fallback_profile()
    if fallback:
        fallback_params = _profile_to_params(fallback, inherit_key=primary_creds.api_key)
        model_list.append({
            "model_name": "fallback",
            "litellm_params": fallback_params,
        })
        logger.debug(f"Router fallback deployment: model={fallback.model}")

    # Configure Router with fallback chain
    # When calling with model="primary", Router will try primary first,
    # then fallback on failure
    router = Router(
        model_list=model_list,
        fallbacks=[{"primary": ["fallback"]}] if fallback else [],
        num_retries=1,  # Retry once on transient errors before fallback
        retry_after=1,  # Wait 1 second before retry
        allowed_fails=1,  # Put deployment in cooldown after 1 failure
        cooldown_time=60,  # Cooldown for 60 seconds
    )

    logger.info(
        f"LLM Router initialized with {len(model_list)} deployment(s)"
        + (f" (fallback: {fallback.model})" if fallback else "")
    )

    return router


def _profile_to_params(
    profile: ModelProfile,
    inherit_key: str | None = None,
) -> dict[str, Any]:
    """Convert a ModelProfile to Router litellm_params format.

    Args:
        profile: The LLM profile to convert.
        inherit_key: API key to use if profile doesn't specify one.

    Returns:
        Dict suitable for litellm_params in Router model_list.
    """
    params: dict[str, Any] = {
        "model": profile.model,
    }

    # Use profile's key, or inherit from primary if not specified
    if profile.api_key:
        params["api_key"] = profile.api_key.get_secret_value()
    elif inherit_key:
        params["api_key"] = inherit_key

    if profile.api_base:
        params["api_base"] = profile.api_base

    return params
