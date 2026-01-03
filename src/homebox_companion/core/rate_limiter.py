"""Rate limiting for LLM API calls using throttled-py.

This module provides rate limiting to prevent hitting OpenAI API limits.
Uses the Token Bucket algorithm with wait-retry mode for smooth throttling.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol, runtime_checkable

from loguru import logger
from throttled.asyncio import RateLimiterType, Throttled, rate_limiter, store

from .config import settings

# Shared memory store for all rate limiters (ensures consistent state)
_memory_store: store.MemoryStore | None = None


def _get_memory_store() -> store.MemoryStore:
    """Get or create the shared memory store."""
    global _memory_store
    if _memory_store is None:
        _memory_store = store.MemoryStore()
    return _memory_store


@lru_cache
def _create_rpm_limiter() -> Throttled:
    """Create the requests-per-minute rate limiter."""
    rpm = settings.rate_limit_rpm
    burst = int(rpm * settings.rate_limit_burst_multiplier)

    logger.debug(f"Creating RPM limiter: {rpm} req/min, burst: {burst}")

    return Throttled(
        using=RateLimiterType.TOKEN_BUCKET.value,
        quota=rate_limiter.per_min(rpm, burst=burst),
        store=_get_memory_store(),  # type: ignore[arg-type]
        # Wait up to 60 seconds for capacity instead of failing immediately
        timeout=60,
    )


@lru_cache
def _create_tpm_limiter() -> Throttled:
    """Create the tokens-per-minute rate limiter."""
    tpm = settings.rate_limit_tpm
    burst = int(tpm * settings.rate_limit_burst_multiplier)

    logger.debug(f"Creating TPM limiter: {tpm} tokens/min, burst: {burst}")

    return Throttled(
        using=RateLimiterType.TOKEN_BUCKET.value,
        quota=rate_limiter.per_min(tpm, burst=burst),
        store=_get_memory_store(),  # type: ignore[arg-type]
        timeout=60,
    )


def is_rate_limiting_enabled() -> bool:
    """Check if rate limiting is enabled."""
    return settings.rate_limit_enabled


def estimate_tokens(messages: list[dict]) -> int:
    """Estimate token count for a message list.

    Uses conservative estimates:
    - Text: ~4 characters per token
    - Images: ~1105 tokens per image (high detail estimate)

    Args:
        messages: List of chat messages to estimate tokens for.

    Returns:
        Estimated token count.
    """
    total_tokens = 0

    for message in messages:
        content = message.get("content", "")

        if isinstance(content, str):
            # Simple text: ~4 chars per token
            total_tokens += len(content) // 4 + 1
        elif isinstance(content, list):
            # Mixed content (text + images)
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    total_tokens += len(text) // 4 + 1
                elif item.get("type") == "image_url":
                    # Conservative estimate for high-detail image
                    total_tokens += 1105

    # Add overhead for message structure
    total_tokens += len(messages) * 4

    return max(total_tokens, 100)  # Minimum 100 tokens


@runtime_checkable
class _Limiter(Protocol):
    async def limit(self, key: str, cost: int) -> object:  # pragma: no cover
        """Acquire quota for a key/cost. Returns a throttled-py result object."""


async def acquire_rate_limit(
    estimated_tokens: int = 1000,
    *,
    rpm_limiter: _Limiter | None = None,
    tpm_limiter: _Limiter | None = None,
    enabled: bool | None = None,
) -> None:
    """Acquire rate limit before making an LLM API call.

    This function will wait (up to 60 seconds) if rate limits are exceeded,
    rather than failing immediately. This provides smoother handling of
    burst traffic.

    Args:
        estimated_tokens: Estimated number of tokens for this request.

    Raises:
        throttled.exceptions.LimitedError: If wait timeout is exceeded.
    """
    if enabled is None:
        enabled = is_rate_limiting_enabled()

    if not enabled:
        return

    if rpm_limiter is None:
        rpm_limiter = _create_rpm_limiter()
    if tpm_limiter is None:
        tpm_limiter = _create_tpm_limiter()

    # Check RPM limit (1 request)
    rpm_result = await rpm_limiter.limit("llm_rpm", cost=1)
    if rpm_result.limited:  # type: ignore[attr-defined]
        logger.debug(
            f"RPM limit reached, waited for capacity. "
            f"Remaining: {rpm_result.state.remaining}, "  # type: ignore[attr-defined]
            f"Reset after: {rpm_result.state.reset_after:.1f}s"  # type: ignore[attr-defined]
        )

    # Check TPM limit (estimated tokens)
    tpm_result = await tpm_limiter.limit("llm_tpm", cost=estimated_tokens)
    if tpm_result.limited:  # type: ignore[attr-defined]
        logger.debug(
            f"TPM limit reached, waited for capacity. "
            f"Remaining: {tpm_result.state.remaining}, "  # type: ignore[attr-defined]
            f"Reset after: {tpm_result.state.reset_after:.1f}s"  # type: ignore[attr-defined]
        )


def clear_rate_limiter_cache() -> None:
    """Clear the rate limiter cache (useful for testing)."""
    global _memory_store
    _memory_store = None
    _create_rpm_limiter.cache_clear()
    _create_tpm_limiter.cache_clear()
