"""Unit tests for LLM fallback logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import litellm
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


@pytest.fixture
def mock_primary_profile() -> MagicMock:
    """Create a mock primary profile with default test values."""
    profile = MagicMock()
    profile.name = "primary"
    profile.model = "primary-model"
    profile.api_key.get_secret_value.return_value = "primary-key"
    profile.api_base = "https://primary.api"
    return profile


class TestLLMFallback:
    """Tests for _with_fallback wrapper function."""

    async def test_primary_success_no_fallback_called(
        self, mock_primary_profile: MagicMock
    ) -> None:
        """If primary succeeds, fallback should not be checked or called."""
        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary_profile),
            patch("homebox_companion.ai.llm.get_fallback_profile") as mock_get_fallback,
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.return_value = {"result": "success"}

            result = await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model=None,  # Will be resolved from primary profile
                api_key=None,
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            assert result == {"result": "success"}
            assert mock_completion.call_count == 1
            mock_get_fallback.assert_not_called()

    async def test_primary_fails_no_fallback_configured_raises(
        self, mock_primary_profile: MagicMock
    ) -> None:
        """If primary fails and no fallback profile exists, error should propagate."""
        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary_profile),
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=None),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = LLMServiceError("Primary failed")

            with pytest.raises(LLMServiceError, match="Primary failed"):
                await llm._with_fallback(
                    messages=[{"role": "user", "content": "test"}],
                    model=None,
                    api_key=None,
                    api_base=None,
                    response_format=None,
                    expected_keys=None,
                )

            assert mock_completion.call_count == 1

    async def test_primary_fails_fallback_succeeds(
        self, mock_primary_profile: MagicMock, mock_fallback_profile: MagicMock
    ) -> None:
        """If primary fails, should switch to fallback."""
        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary_profile),
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
                model=None,
                api_key=None,
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            # Check result
            assert result == {"result": "fallback success"}

            # Verify orchestration logic
            assert mock_completion.call_count == 2

            # Primary call - uses resolved primary profile
            _, kwargs1 = mock_completion.call_args_list[0]
            assert kwargs1["model"] == "primary-model"

            # Fallback call
            _, kwargs2 = mock_completion.call_args_list[1]
            assert kwargs2["model"] == "fallback-model"
            assert kwargs2["api_key"] == "fallback-key"
            assert kwargs2["api_base"] == "https://fallback.api"

    async def test_both_primary_and_fallback_fail(
        self, mock_primary_profile: MagicMock
    ) -> None:
        """If both fail, should raise the fallback's exception."""
        mock_fallback = MagicMock()
        mock_fallback.model = "fallback-model"
        # Test inheritance: api_key is None, should use primary's
        mock_fallback.api_key = None
        mock_fallback.api_base = None

        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary_profile),
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=mock_fallback),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = [
                LLMServiceError("Primary error"),
                LLMServiceError("Fallback error"),
            ]

            with pytest.raises(LLMServiceError, match="Fallback error"):
                await llm._with_fallback(
                    messages=[{"role": "user", "content": "test"}],
                    model=None,
                    api_key=None,
                    api_base=None,
                    response_format=None,
                    expected_keys=None,
                )

            assert mock_completion.call_count == 2

            # Verify inheritance logic - fallback call should reuse primary credentials
            _, kwargs2 = mock_completion.call_args_list[1]
            assert kwargs2["api_key"] == "primary-key"  # Inherited from primary
            assert kwargs2["api_base"] is None  # Fallback's api_base takes precedence

    async def test_non_llm_error_propagates_without_fallback(
        self, mock_primary_profile: MagicMock
    ) -> None:
        """Non-LLMServiceError exceptions should propagate immediately without fallback."""
        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary_profile),
            patch("homebox_companion.ai.llm.get_fallback_profile") as mock_get_fallback,
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = ValueError("Unexpected error")

            with pytest.raises(ValueError, match="Unexpected error"):
                await llm._with_fallback(
                    messages=[{"role": "user", "content": "test"}],
                    model=None,
                    api_key=None,
                    api_base=None,
                    response_format=None,
                    expected_keys=None,
                )

            # Should not attempt fallback for non-LLMServiceError
            assert mock_completion.call_count == 1
            mock_get_fallback.assert_not_called()

    async def test_response_format_and_expected_keys_passed_through(
        self, mock_primary_profile: MagicMock, mock_fallback_profile: MagicMock
    ) -> None:
        """Verify response_format and expected_keys are passed to both primary and fallback."""
        test_response_format = {"type": "json_object"}
        test_expected_keys = ["name", "description"]

        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary_profile),
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=mock_fallback_profile),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.side_effect = [
                LLMServiceError("Primary error"),
                {"name": "test", "description": "test desc"},
            ]

            await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model=None,
                api_key=None,
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


class TestPrimaryProfileResolution:
    """Tests for PRIMARY profile resolution (the bug fix)."""

    async def test_uses_primary_profile_when_configured(self) -> None:
        """If PRIMARY profile exists, use its credentials instead of env vars."""
        mock_primary = MagicMock()
        mock_primary.name = "anthropic"
        mock_primary.model = "claude-3-opus"
        mock_primary.api_key.get_secret_value.return_value = "anthropic-key"
        mock_primary.api_base = "https://api.anthropic.com"

        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary),
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=None),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.return_value = {"result": "success"}

            # Call WITHOUT explicit model/key → should resolve from PRIMARY
            await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model=None,
                api_key=None,
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            # Verify PRIMARY profile was used
            _, kwargs = mock_completion.call_args
            assert kwargs["model"] == "claude-3-opus"
            assert kwargs["api_key"] == "anthropic-key"
            assert kwargs["api_base"] == "https://api.anthropic.com"

    async def test_falls_back_to_env_when_no_primary_profile(self) -> None:
        """If no PRIMARY profile, use environment variable defaults."""
        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=None),
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=None),
            patch("homebox_companion.core.llm_utils.config") as mock_config,
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_config.settings.effective_llm_model = "gpt-5-mini"
            mock_config.settings.effective_llm_api_key = "env-key"
            mock_config.settings.llm_api_base = None
            mock_completion.return_value = {"result": "success"}

            await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model=None,
                api_key=None,
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            _, kwargs = mock_completion.call_args
            assert kwargs["model"] == "gpt-5-mini"
            assert kwargs["api_key"] == "env-key"

    async def test_explicit_args_override_primary_profile(self) -> None:
        """Explicit function arguments take precedence over PRIMARY profile."""
        mock_primary = MagicMock()
        mock_primary.name = "default"
        mock_primary.model = "claude-3-opus"
        mock_primary.api_key.get_secret_value.return_value = "primary-key"
        mock_primary.api_base = None

        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary),
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=None),
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_completion.return_value = {"result": "success"}

            await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model="explicit-model",  # Explicit override
                api_key="explicit-key",  # Explicit override
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            _, kwargs = mock_completion.call_args
            assert kwargs["model"] == "explicit-model"
            assert kwargs["api_key"] == "explicit-key"

    async def test_raises_error_when_no_credentials_available(self) -> None:
        """Raise LLMServiceError if no profile or env vars provide credentials."""
        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=None),
            patch("homebox_companion.core.llm_utils.config") as mock_config,
        ):
            mock_config.settings.effective_llm_model = None
            mock_config.settings.effective_llm_api_key = None
            mock_config.settings.llm_api_base = None

            with pytest.raises(LLMServiceError, match="No API key configured"):
                await llm._with_fallback(
                    messages=[{"role": "user", "content": "test"}],
                    model=None,
                    api_key=None,
                    api_base=None,
                    response_format=None,
                    expected_keys=None,
                )

    async def test_primary_profile_without_api_key_falls_back_to_env_key(self) -> None:
        """If PRIMARY profile has no api_key, use env var key."""
        mock_primary = MagicMock()
        mock_primary.name = "local-ollama"
        mock_primary.model = "ollama/mistral"
        mock_primary.api_key = None  # Some providers don't need keys
        mock_primary.api_base = "http://localhost:11434"

        with (
            patch("homebox_companion.core.llm_utils.get_primary_profile", return_value=mock_primary),
            patch("homebox_companion.ai.llm.get_fallback_profile", return_value=None),
            patch("homebox_companion.core.llm_utils.config") as mock_config,
            patch("homebox_companion.ai.llm._acompletion_with_repair", new_callable=AsyncMock) as mock_completion,
        ):
            mock_config.settings.effective_llm_api_key = "env-fallback-key"
            mock_config.settings.effective_llm_model = "gpt-5-mini"
            mock_config.settings.llm_api_base = None
            mock_completion.return_value = {"result": "success"}

            await llm._with_fallback(
                messages=[{"role": "user", "content": "test"}],
                model=None,
                api_key=None,
                api_base=None,
                response_format=None,
                expected_keys=None,
            )

            _, kwargs = mock_completion.call_args
            assert kwargs["model"] == "ollama/mistral"  # From profile
            assert kwargs["api_key"] == "env-fallback-key"  # From env (profile had None)
            assert kwargs["api_base"] == "http://localhost:11434"  # From profile


class TestLLMClientProfileResolution:
    """Tests for LLMClient profile resolution (chat completions)."""

    async def test_llm_client_uses_primary_profile(self) -> None:
        """LLMClient should use PRIMARY profile credentials via resolve_llm_credentials."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        # Mock resolve_llm_credentials to return a specific profile
        mock_creds = LLMCredentials(
            model="claude-3-5-sonnet",
            api_key="anthropic-key",
            api_base="https://api.anthropic.com",
            profile_name="anthropic",
        )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_timeout = 30
            mock_config.settings.llm_stream_timeout = 60
            mock_config.settings.chat_max_response_tokens = 0

            client = LLMClient()
            kwargs = client._build_request_kwargs(
                messages=[{"role": "user", "content": "test"}],
                tools=None,
                stream=False,
            )

            # Assert credentials from mock were used
            assert kwargs["model"] == "claude-3-5-sonnet"
            assert kwargs["api_key"] == "anthropic-key"
            assert kwargs["api_base"] == "https://api.anthropic.com"

    async def test_llm_client_falls_back_to_env_when_no_primary(self) -> None:
        """LLMClient should fall back to env vars via resolve_llm_credentials."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        # Mock resolve_llm_credentials to return env defaults (no profile)
        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="env-key",
            api_base=None,
            profile_name=None,  # No profile used
        )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_timeout = 30
            mock_config.settings.llm_stream_timeout = 60
            mock_config.settings.chat_max_response_tokens = 0

            client = LLMClient()
            kwargs = client._build_request_kwargs(
                messages=[{"role": "user", "content": "test"}],
                tools=None,
                stream=True,
            )

            assert kwargs["model"] == "gpt-5-mini"
            assert kwargs["api_key"] == "env-key"
            assert "api_base" not in kwargs  # None is not included


class TestLLMClientFallback:
    """Tests for LLMClient.complete() and complete_stream() fallback behavior."""

    async def test_complete_uses_fallback_on_primary_failure(
        self, mock_fallback_profile: MagicMock
    ) -> None:
        """LLMClient.complete() should use fallback when primary fails."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="primary-model",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        # Mock response for fallback
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "fallback response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = None

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch("homebox_companion.chat.llm_client.get_fallback_profile", return_value=mock_fallback_profile),
            patch("homebox_companion.chat.llm_client.litellm.acompletion", new_callable=AsyncMock) as mock_completion,
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_timeout = 30
            mock_config.settings.chat_max_response_tokens = 0

            # Primary fails with specific litellm exception, fallback succeeds
            mock_completion.side_effect = [
                litellm.APIConnectionError(
                    message="Primary connection failed",
                    llm_provider="openai",
                    model="primary-model",
                ),
                mock_response,
            ]

            client = LLMClient()
            result = await client.complete(messages=[{"role": "user", "content": "test"}])

            assert result.content == "fallback response"
            assert mock_completion.call_count == 2

            # Verify fallback credentials were used on second call
            _, kwargs2 = mock_completion.call_args_list[1]
            assert kwargs2["model"] == "fallback-model"
            assert kwargs2["api_key"] == "fallback-key"

    async def test_complete_stream_uses_fallback_on_primary_failure(
        self, mock_fallback_profile: MagicMock
    ) -> None:
        """LLMClient.complete_stream() should use fallback when primary fails."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="primary-model",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        # Mock async generator for streaming response
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk1"))])
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk2"))])

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch("homebox_companion.chat.llm_client.get_fallback_profile", return_value=mock_fallback_profile),
            patch("homebox_companion.chat.llm_client.litellm.acompletion", new_callable=AsyncMock) as mock_completion,
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_stream_timeout = 60
            mock_config.settings.chat_max_response_tokens = 0

            # Primary fails with specific litellm exception, fallback returns stream
            mock_completion.side_effect = [
                litellm.APIConnectionError(
                    message="Primary connection failed",
                    llm_provider="openai",
                    model="primary-model",
                ),
                mock_stream(),
            ]

            client = LLMClient()
            chunks = []
            async for chunk in client.complete_stream(messages=[{"role": "user", "content": "test"}]):
                chunks.append(chunk)

            assert len(chunks) == 2
            assert mock_completion.call_count == 2

            # Verify fallback credentials were used
            _, kwargs2 = mock_completion.call_args_list[1]
            assert kwargs2["model"] == "fallback-model"

    async def test_complete_no_fallback_when_not_configured(self) -> None:
        """LLMClient.complete() should raise if no fallback configured."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="primary-model",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch("homebox_companion.chat.llm_client.get_fallback_profile", return_value=None),
            patch("homebox_companion.chat.llm_client.litellm.acompletion", new_callable=AsyncMock) as mock_completion,
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_timeout = 30
            mock_config.settings.chat_max_response_tokens = 0

            mock_completion.side_effect = litellm.APIConnectionError(
                message="Primary failed",
                llm_provider="openai",
                model="primary-model",
            )

            client = LLMClient()
            with pytest.raises(litellm.APIConnectionError):
                await client.complete(messages=[{"role": "user", "content": "test"}])

            # Should only call once (no fallback attempt)
            assert mock_completion.call_count == 1


class TestLLMClientMidStreamFailure:
    """Tests verifying mid-stream failures are NOT caught by fallback.

    The fallback mechanism only handles initial connection errors.
    Once streaming starts, errors propagate to the caller.
    """

    async def test_mid_stream_error_propagates_without_fallback(
        self, mock_fallback_profile: MagicMock
    ) -> None:
        """Errors during stream iteration should propagate, not trigger fallback."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="primary-model",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        # Mock async generator that fails mid-stream
        async def failing_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk1"))])
            raise litellm.APIError(
                message="Stream interrupted",
                llm_provider="openai",
                model="primary-model",
                status_code=500,
            )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch("homebox_companion.chat.llm_client.get_fallback_profile", return_value=mock_fallback_profile),
            patch("homebox_companion.chat.llm_client.litellm.acompletion", new_callable=AsyncMock) as mock_completion,
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_stream_timeout = 60
            mock_config.settings.chat_max_response_tokens = 0

            # Primary connection succeeds, but stream fails mid-way
            mock_completion.return_value = failing_stream()

            client = LLMClient()
            chunks = []

            # Should raise during iteration, NOT retry with fallback
            with pytest.raises(litellm.APIError, match="Stream interrupted"):
                async for chunk in client.complete_stream(messages=[{"role": "user", "content": "test"}]):
                    chunks.append(chunk)

            # Only one call made (no fallback retry)
            assert mock_completion.call_count == 1
            # First chunk was received before failure
            assert len(chunks) == 1
