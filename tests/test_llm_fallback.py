"""Unit tests for LLM fallback logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homebox_companion.ai import llm
from homebox_companion.core.exceptions import LLMServiceError


pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def mock_fallback_profile() -> MagicMock:
    """Create a mock fallback profile with default test values."""
    profile = MagicMock()
    profile.model = "fallback-model"
    profile.api_key.get_secret_value.return_value = "fallback-key"
    profile.api_base = "https://fallback.api"
    return profile


class TestLLMFallback:
    """Tests for _with_fallback wrapper function."""

    async def test_primary_success_no_fallback_called(self) -> None:
        """If primary succeeds, fallback should not be checked or called."""
        with (
            patch("homebox_companion.ai.llm.get_fallback_profile") as mock_get_profile,
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.return_value = {"result": "success"}

            result = await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model="primary-model",
                api_key="primary-key",
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            assert result == {"result": "success"}
            assert mock_completion.call_count == 1
            mock_get_profile.assert_not_called()

    async def test_primary_fails_no_fallback_configured_raises(self) -> None:
        """If primary fails and no fallback profile exists, error should propagate."""
        with (
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=None),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = LLMServiceError("Primary failed")

            with pytest.raises(LLMServiceError, match="Primary failed"):
                await llm._with_fallback(
                    messages=[{"role": "user", "content": "test"}],
                    model="primary-model",
                    api_key="primary-key",
                    api_base=None,
                    response_format=None,
                    expected_keys=None,
                )

            assert mock_completion.call_count == 1

    async def test_primary_fails_fallback_succeeds(
        self, mock_fallback_profile: MagicMock
    ) -> None:
        """If primary fails, should switch to fallback."""
        with (
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=mock_fallback_profile),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            # Fail first, succeed second
            mock_completion.side_effect = [
                LLMServiceError("Primary error"),
                {"result": "fallback success"},
            ]

            result = await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model="primary-model",
                api_key="primary-key",
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            # Check result
            assert result == {"result": "fallback success"}

            # Verify orchestration logic
            assert mock_completion.call_count == 2

            # Primary call
            _, kwargs1 = mock_completion.call_args_list[0]
            assert kwargs1["model"] == "primary-model"

            # Fallback call
            _, kwargs2 = mock_completion.call_args_list[1]
            assert kwargs2["model"] == "fallback-model"
            assert kwargs2["api_key"] == "fallback-key"
            assert kwargs2["api_base"] == "https://fallback.api"

    async def test_both_primary_and_fallback_fail(self) -> None:
        """If both fail, should raise the fallback's exception."""
        mock_profile = MagicMock()
        mock_profile.model = "fallback-model"
        # Test inheritance: api_key is None, should use primary's
        mock_profile.api_key = None
        mock_profile.api_base = None

        with (
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=mock_profile),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = [
                LLMServiceError("Primary error"),
                LLMServiceError("Fallback error"),
            ]

            with pytest.raises(LLMServiceError, match="Fallback error"):
                await llm._with_fallback(
                    messages=[{"role": "user", "content": "test"}],
                    model="primary-model",
                    api_key="primary-key",  # Should be passed through
                    api_base="https://primary.api",  # Should be passed through
                    response_format=None,
                    expected_keys=None,
                )

            assert mock_completion.call_count == 2

            # Verify inheritance logic - fallback call should reuse primary credentials
            _, kwargs2 = mock_completion.call_args_list[1]
            assert kwargs2["api_key"] == "primary-key"
            assert kwargs2["api_base"] is None  # Fallback's api_base takes precedence

    async def test_non_llm_error_propagates_without_fallback(self) -> None:
        """Non-LLMServiceError exceptions should propagate immediately without fallback."""
        with (
            patch("homebox_companion.ai.llm.get_fallback_profile") as mock_get_profile,
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = ValueError("Unexpected error")

            with pytest.raises(ValueError, match="Unexpected error"):
                await llm._with_fallback(
                    messages=[{"role": "user", "content": "test"}],
                    model="primary-model",
                    api_key="primary-key",
                    api_base=None,
                    response_format=None,
                    expected_keys=None,
                )

            # Should not attempt fallback for non-LLMServiceError
            assert mock_completion.call_count == 1
            mock_get_profile.assert_not_called()

    async def test_response_format_and_expected_keys_passed_through(
        self, mock_fallback_profile: MagicMock
    ) -> None:
        """Verify response_format and expected_keys are passed to both primary and fallback."""
        test_response_format = {"type": "json_object"}
        test_expected_keys = ["name", "description"]

        with (
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=mock_fallback_profile),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = [
                LLMServiceError("Primary error"),
                {"name": "test", "description": "test desc"},
            ]

            await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model="primary-model",
                api_key="primary-key",
                api_base=None,
                response_format=test_response_format,
                expected_keys=test_expected_keys,
            )

            # Verify both calls received the same response_format and expected_keys
            _, kwargs1 = mock_completion.call_args_list[0]
            assert kwargs1["response_format"] == test_response_format
            assert kwargs1["expected_keys"] == test_expected_keys

            _, kwargs2 = mock_completion.call_args_list[1]
            assert kwargs2["response_format"] == test_response_format
            assert kwargs2["expected_keys"] == test_expected_keys
