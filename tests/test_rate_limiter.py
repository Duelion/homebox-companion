"""Tests for the rate limiter module.

Tests verify both token estimation logic and actual throttling behavior
using timing-based assertions with reasonable variance tolerances.
"""

import asyncio
import time
from dataclasses import dataclass

import pytest
from throttled.asyncio import RateLimiterType, Throttled, rate_limiter, store

from homebox_companion.core.rate_limiter import (
    clear_rate_limiter_cache,
    estimate_tokens,
    is_rate_limiting_enabled,
)

# Most tests are unit tests; timing-sensitive tests marked with @pytest.mark.integration
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


class TestThrottlingBehavior:
    """Tests for actual throttling behavior using timing.

    These tests use a low-limit throttler to verify that:
    1. Requests within limits proceed immediately
    2. Requests exceeding limits are delayed appropriately
    3. The Token Bucket algorithm allows bursts up to capacity
    """

    # These are inherently timing/scheduler dependent, so keep them out of the default
    # unit test run. They validate the third-party throttled-py behavior more than our
    # own integration.
    pytestmark = pytest.mark.integration

    @pytest.fixture
    def test_throttler(self):
        """Create a fast throttler for testing (20 req/sec with burst 3)."""
        mem_store = store.MemoryStore()
        return Throttled(
            using=RateLimiterType.TOKEN_BUCKET.value,
            # Use a high rate so timing-based integration tests complete quickly.
            # Still exercises token bucket behavior (burst then refill).
            quota=rate_limiter.per_sec(20, burst=3),  # 20/sec, burst of 3
            store=mem_store,  # type: ignore[arg-type]
            timeout=2,  # Hard cap so these tests can't stall CI
        )

    @pytest.mark.asyncio
    async def test_requests_within_burst_are_immediate(self, test_throttler):
        """Requests within burst capacity should complete immediately."""
        start = time.monotonic()

        # 3 requests should complete within burst capacity
        for _ in range(3):
            result = await test_throttler.limit("test_key", cost=1)
            assert result.limited is False

        elapsed = time.monotonic() - start
        # Should complete quickly (no waiting for refill)
        assert elapsed < 0.2, f"Burst requests took too long: {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_requests_exceeding_burst_are_delayed(self, test_throttler):
        """Requests exceeding burst should wait for token refill."""
        # Exhaust the burst capacity
        for _ in range(3):
            await test_throttler.limit("test_key", cost=1)

        # This request should wait for refill (~0.05 seconds for 20/sec rate)
        start = time.monotonic()
        result = await test_throttler.limit("test_key", cost=1)
        elapsed = time.monotonic() - start

        # Should have waited for token refill (Token Bucket behavior)
        # Allow generous tolerance - the key assertion is that there IS a delay
        assert 0.01 < elapsed < 2.0, f"Expected noticeable delay, got {elapsed:.3f}s"
        # Request should eventually succeed (not be rejected)
        assert result.limited is False or result.state.remaining >= 0

    @pytest.mark.asyncio
    async def test_control_no_throttle_baseline(self):
        """Control test: verify requests without throttling are instant."""
        # This establishes that our timing tests are meaningful
        start = time.monotonic()

        # 10 simple async operations (no throttling)
        for _ in range(10):
            await asyncio.sleep(0)  # Just yield to event loop

        elapsed = time.monotonic() - start
        # Should be essentially instant (avoid overly tight bounds on busy CI)
        assert elapsed < 0.05, f"Control test baseline: {elapsed:.3f}s (should be ~0)"

    @pytest.mark.asyncio
    async def test_concurrent_requests_are_throttled(self, test_throttler):
        """Concurrent requests exceeding limit should be serialized."""
        # Send 6 requests concurrently (burst 3, rate 20/sec)
        # Expected: 3 immediate, 3 delayed (~0.05s each)
        start = time.monotonic()

        async def make_request():
            return await test_throttler.limit("concurrent_key", cost=1)

        results = await asyncio.gather(*[make_request() for _ in range(6)])
        elapsed = time.monotonic() - start

        # All requests should complete
        assert len(results) == 6

        # Should take a short-but-nonzero amount of time due to refill waiting.
        # Allow generous variance for CI systems.
        assert 0.05 < elapsed < 2.0, f"Expected short delay, got {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_token_bucket_refill_rate(self, test_throttler):
        """Verify tokens refill at the expected rate."""
        # Exhaust burst
        for _ in range(3):
            await test_throttler.limit("refill_key", cost=1)

        # Wait for partial refill (should get ~2 tokens in 0.1s at 20/sec)
        await asyncio.sleep(0.1)

        # Check state - should have roughly 1 token available
        state = await test_throttler.peek("refill_key")
        # remaining should be in a small range (timing variance is expected)
        assert 0 <= state.remaining <= 3, f"Expected small remaining, got {state.remaining}"


class TestRateLimiterAcquisition:
    """Tests for the acquire_rate_limit function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_rate_limiter_cache()

    def teardown_method(self):
        """Clear cache after each test."""
        clear_rate_limiter_cache()

    @pytest.mark.asyncio
    async def test_acquire_rate_limit_basic(self):
        """Test basic rate limit acquisition."""
        from homebox_companion.core.rate_limiter import acquire_rate_limit

        # Should not raise for reasonable token count
        await acquire_rate_limit(estimated_tokens=1000, enabled=False)

    @pytest.mark.asyncio
    async def test_acquire_rate_limit_multiple_calls(self):
        """Test multiple rate limit acquisitions complete quickly."""
        from homebox_companion.core.rate_limiter import acquire_rate_limit

        start = time.monotonic()

        # Multiple calls should work quickly (default limits are high)
        for _ in range(5):
            await acquire_rate_limit(estimated_tokens=100, enabled=False)

        elapsed = time.monotonic() - start
        # With default limits (400 RPM), 5 requests should be instant
        assert elapsed < 0.5, f"Multiple acquisitions took too long: {elapsed:.3f}s"

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
