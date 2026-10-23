"""Tests for the rate limiter module.

Tests verify our token estimates and limiter wiring without scheduler timing.
"""

from dataclasses import dataclass

import pytest

from homebox_companion.core.rate_limiter import (
    clear_rate_limiter_cache,
    estimate_tokens,
    is_rate_limiting_enabled,
)

# These tests exercise our integration with the limiter using deterministic fakes.
pytestmark = pytest.mark.unit


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_estimate_tokens_simple_text(self):
        """Test token estimation for simple text messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, world!"},
        ]
        tokens = estimate_tokens(messages)
        # Should be at least 100 (our minimum)
        assert tokens >= 100
        # Should be reasonable for short messages
        assert tokens < 500

    def test_estimate_tokens_with_images(self):
        """Test token estimation for messages with images."""
        messages = [
            {"role": "system", "content": "Analyze this image."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
                ],
            },
        ]
        tokens = estimate_tokens(messages)
        # Should include ~1105 tokens for the image
        assert tokens >= 1105
        # Should be reasonable
        assert tokens < 2000

    def test_estimate_tokens_multiple_images(self):
        """Test token estimation for multiple images."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Compare these images."},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,def"}},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,ghi"}},
                ],
            },
        ]
        tokens = estimate_tokens(messages)
        # Should include ~1105 tokens per image (3 images)
        assert tokens >= 3 * 1105
        # Should be reasonable
        assert tokens < 5000

    def test_estimate_tokens_empty_messages(self):
        """Test token estimation for empty message list."""
        messages = []
        tokens = estimate_tokens(messages)
        # Should return minimum of 100
        assert tokens == 100

    def test_estimate_tokens_long_text(self):
        """Test token estimation for long text content."""
        long_text = "x" * 4000  # ~1000 tokens worth
        messages = [{"role": "user", "content": long_text}]
        tokens = estimate_tokens(messages)
        # Should be proportional to text length
        assert tokens >= 1000
        assert tokens < 1500


class TestRateLimiterConfiguration:
    """Tests for rate limiter configuration."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_rate_limiter_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_rate_limiter_cache()

    def test_is_rate_limiting_enabled_default(self):
        """Test that rate limiting is enabled by default."""
        # Note: This uses the default settings which have rate_limit_enabled=True
        assert is_rate_limiting_enabled() is True


class TestRateLimiterAcquisition:
    """Tests for the acquire_rate_limit function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_rate_limiter_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_rate_limiter_cache()

    @pytest.mark.asyncio
    async def test_acquire_rate_limit_calls_rpm_and_tpm_with_expected_costs(self):
        """Unit test: acquire_rate_limit uses the expected keys and costs (no timing)."""
        from homebox_companion.core.rate_limiter import acquire_rate_limit

        @dataclass(frozen=True)
        class _State:
            remaining: int = 0
            reset_after: float = 0.0

        @dataclass(frozen=True)
        class _Result:
            limited: bool = False
            state: _State = _State()

        class _FakeLimiter:
            def __init__(self) -> None:
                self.calls: list[tuple[str, int]] = []

            async def limit(self, key: str, cost: int) -> _Result:
                self.calls.append((key, cost))
                return _Result(limited=False)

        rpm = _FakeLimiter()
        tpm = _FakeLimiter()

        await acquire_rate_limit(
            estimated_tokens=1234,
            rpm_limiter=rpm,
            tpm_limiter=tpm,
            enabled=True,
        )

        assert rpm.calls == [("llm_rpm", 1)]
        assert tpm.calls == [("llm_tpm", 1234)]

    @pytest.mark.asyncio
    async def test_acquire_rate_limit_disabled_does_not_touch_limiters(self):
        """Unit test: disabled rate limiting short-circuits without calling limiters."""
        from homebox_companion.core.rate_limiter import acquire_rate_limit

        class _FakeLimiter:
            def __init__(self) -> None:
                self.called = False

            async def limit(self, key: str, cost: int) -> object:  # pragma: no cover
                self.called = True
                raise AssertionError("Limiter should not be called when disabled")

        rpm = _FakeLimiter()
        tpm = _FakeLimiter()

        await acquire_rate_limit(
            estimated_tokens=999,
            rpm_limiter=rpm,
            tpm_limiter=tpm,
            enabled=False,
        )

        assert rpm.called is False
        assert tpm.called is False

    @pytest.mark.asyncio
    async def test_acquire_rate_limit_handles_limited_results(self):
        """Unit test: limited=True results are tolerated (logging path)."""
        from homebox_companion.core.rate_limiter import acquire_rate_limit

        @dataclass(frozen=True)
        class _State:
            remaining: int = -1
            reset_after: float = 1.25

        @dataclass(frozen=True)
        class _Result:
            limited: bool
            state: _State = _State()

        class _FakeLimiter:
            def __init__(self, limited: bool) -> None:
                self.limited = limited
                self.calls: list[tuple[str, int]] = []

            async def limit(self, key: str, cost: int) -> _Result:
                self.calls.append((key, cost))
                return _Result(limited=self.limited)

        rpm = _FakeLimiter(limited=True)
        tpm = _FakeLimiter(limited=True)

        await acquire_rate_limit(
            estimated_tokens=2500,
            rpm_limiter=rpm,
            tpm_limiter=tpm,
            enabled=True,
        )

        assert rpm.calls == [("llm_rpm", 1)]
        assert tpm.calls == [("llm_tpm", 2500)]
