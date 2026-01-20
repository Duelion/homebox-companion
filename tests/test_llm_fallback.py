"""Unit tests for LLM fallback logic via LiteLLM Router.

Tests verify:
- Router is built correctly from profiles
- Fallback configuration works
- Router invalidation triggers rebuild
- Profile resolution for capability checks
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homebox_companion.core.llm_router import (
    _build_router_from_profiles,
    get_primary_model_name,
    get_router,
    invalidate_router,
)


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def reset_router():
    """Reset Router singleton before each test."""
    invalidate_router()
    yield
    invalidate_router()


class TestRouterConstruction:
    """Tests for Router singleton construction and configuration."""

    def test_get_primary_model_name_returns_primary(self) -> None:
        """The model_name for primary deployments should be 'primary'."""
        assert get_primary_model_name() == "primary"

    def test_router_built_from_primary_profile(self) -> None:
        """Router should be built with primary profile credentials."""
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
        ):
            router = _build_router_from_profiles()

            # Router should have one deployment
            assert len(router.model_list) == 1
            assert router.model_list[0]["model_name"] == "primary"
            assert router.model_list[0]["litellm_params"]["model"] == "gpt-5-mini"
            assert router.model_list[0]["litellm_params"]["api_key"] == "primary-key"

    def test_router_includes_fallback_deployment(self) -> None:
        """Router should include fallback deployment when configured."""
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        # Create mock fallback profile
        mock_fallback = MagicMock()
        mock_fallback.model = "claude-sonnet-4-20250514"
        mock_fallback.api_key = MagicMock()
        mock_fallback.api_key.get_secret_value.return_value = "fallback-key"
        mock_fallback.api_base = "https://api.anthropic.com"

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=mock_fallback,
            ),
        ):
            router = _build_router_from_profiles()

            # Router should have two deployments
            assert len(router.model_list) == 2
            assert router.model_list[0]["model_name"] == "primary"
            assert router.model_list[1]["model_name"] == "fallback"
            assert router.model_list[1]["litellm_params"]["model"] == "claude-sonnet-4-20250514"

    def test_router_fallback_inherits_api_key(self) -> None:
        """Fallback should inherit primary's API key if not specified."""
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        # Fallback without api_key
        mock_fallback = MagicMock()
        mock_fallback.model = "gpt-4o"
        mock_fallback.api_key = None  # No key specified
        mock_fallback.api_base = None

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=mock_fallback,
            ),
        ):
            router = _build_router_from_profiles()

            # Fallback should inherit primary's key
            assert router.model_list[1]["litellm_params"]["api_key"] == "primary-key"


class TestRouterSingleton:
    """Tests for Router singleton behavior."""

    def test_get_router_returns_same_instance(self) -> None:
        """get_router should return the same instance on repeated calls."""
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="test-key",
            api_base=None,
            profile_name="test",
        )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
        ):
            router1 = get_router()
            router2 = get_router()

            assert router1 is router2

    def test_invalidate_router_clears_singleton(self) -> None:
        """invalidate_router should force new Router on next access."""
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="test-key",
            api_base=None,
            profile_name="test",
        )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
        ):
            router1 = get_router()
            invalidate_router()
            router2 = get_router()

            # Should be different instances after invalidation
            assert router1 is not router2


class TestRouterFallbackBehavior:
    """Tests for Router fallback execution."""

    @pytest.mark.asyncio
    async def test_router_fallback_chain_configured(self) -> None:
        """Router should be configured with fallback chain when fallback exists."""
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="primary-key",
            api_base=None,
            profile_name="primary",
        )

        # Create mock fallback profile
        mock_fallback = MagicMock()
        mock_fallback.model = "claude-sonnet-4-20250514"
        mock_fallback.api_key = MagicMock()
        mock_fallback.api_key.get_secret_value.return_value = "fallback-key"
        mock_fallback.api_base = "https://api.anthropic.com"

        # Mock a successful response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success from fallback"
        mock_response.usage = None

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=mock_fallback,
            ),
        ):
            router = get_router()

            # Patch the router's acompletion to verify it was configured correctly
            # The Router's fallback configuration is what we're testing
            assert router.fallbacks is not None
            assert {"primary": ["fallback"]} in router.fallbacks


class TestLLMClientWithRouter:
    """Tests for LLMClient using Router."""

    @pytest.mark.asyncio
    async def test_llm_client_uses_router(self) -> None:
        """LLMClient.complete should use Router for completion."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="test-key",
            api_base=None,
            profile_name="test",
        )

        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_timeout = 30
            mock_config.settings.chat_max_response_tokens = 0

            client = LLMClient()

            # Get the router and mock its acompletion
            router = get_router()
            with patch.object(router, "acompletion", new_callable=AsyncMock) as mock_completion:
                mock_completion.return_value = mock_response

                result = await client.complete(
                    messages=[{"role": "user", "content": "test"}]
                )

                assert result.content == "Test response"
                mock_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_client_streaming_uses_router(self) -> None:
        """LLMClient.complete_stream should use Router for streaming completion."""
        from homebox_companion.chat.llm_client import LLMClient
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="test-key",
            api_base=None,
            profile_name="test",
        )

        # Mock streaming response
        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk1"))])
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="chunk2"))])

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
            patch("homebox_companion.chat.llm_client.config") as mock_config,
        ):
            mock_config.settings.llm_stream_timeout = 60
            mock_config.settings.chat_max_response_tokens = 0

            client = LLMClient()
            router = get_router()

            with patch.object(router, "acompletion", new_callable=AsyncMock) as mock_completion:
                mock_completion.return_value = mock_stream()

                chunks = []
                async for chunk in client.complete_stream(
                    messages=[{"role": "user", "content": "test"}]
                ):
                    chunks.append(chunk)

                assert len(chunks) == 2
                mock_completion.assert_called_once()


class TestJsonCompletionWithRouter:
    """Tests for json_completion using Router."""

    @pytest.mark.asyncio
    async def test_json_completion_uses_router(self) -> None:
        """json_completion should route through Router."""
        from homebox_companion.ai.json_completion import json_completion
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="test-key",
            api_base=None,
            profile_name="test",
        )

        # Mock response with valid JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "Test Item", "description": "A test"}'
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
            patch("homebox_companion.ai.json_completion.config") as mock_config,
            patch(
                "homebox_companion.ai.json_completion.is_rate_limiting_enabled",
                return_value=False,
            ),
        ):
            mock_config.settings.llm_timeout = 30

            router = get_router()
            with patch.object(router, "acompletion", new_callable=AsyncMock) as mock_completion:
                mock_completion.return_value = mock_response

                result = await json_completion(
                    messages=[{"role": "user", "content": "describe this item"}],
                    expected_keys=["name", "description"],
                )

                assert result == {"name": "Test Item", "description": "A test"}
                mock_completion.assert_called_once()

    @pytest.mark.asyncio
    async def test_json_completion_triggers_repair_on_invalid_json(self) -> None:
        """json_completion should attempt repair when JSON is invalid."""
        from homebox_companion.ai.json_completion import json_completion
        from homebox_companion.core.llm_utils import LLMCredentials

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="test-key",
            api_base=None,
            profile_name="test",
        )

        # First response is invalid JSON, second is repaired
        invalid_response = MagicMock()
        invalid_response.choices = [MagicMock()]
        invalid_response.choices[0].message.content = "{name: 'broken'"
        invalid_response.usage = None

        valid_response = MagicMock()
        valid_response.choices = [MagicMock()]
        valid_response.choices[0].message.content = '{"name": "Fixed"}'
        valid_response.usage = None

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
            patch("homebox_companion.ai.json_completion.config") as mock_config,
            patch(
                "homebox_companion.ai.json_completion.is_rate_limiting_enabled",
                return_value=False,
            ),
        ):
            mock_config.settings.llm_timeout = 30

            router = get_router()
            with patch.object(router, "acompletion", new_callable=AsyncMock) as mock_completion:
                mock_completion.side_effect = [invalid_response, valid_response]

                result = await json_completion(
                    messages=[{"role": "user", "content": "describe this item"}],
                    expected_keys=["name"],
                )

                assert result == {"name": "Fixed"}
                # Should have called twice: initial + repair
                assert mock_completion.call_count == 2


class TestSettingsInvalidation:
    """Tests for Router invalidation when settings change."""

    def test_save_settings_invalidates_router(self) -> None:
        """Saving settings should invalidate the Router singleton."""
        from homebox_companion.core.llm_utils import LLMCredentials
        from homebox_companion.core.persistent_settings import (
            ModelProfile,
            PersistentSettings,
            ProfileStatus,
            save_settings,
        )

        mock_creds = LLMCredentials(
            model="gpt-5-mini",
            api_key="test-key",
            api_base=None,
            profile_name="test",
        )

        with (
            patch(
                "homebox_companion.core.llm_utils.resolve_llm_credentials",
                return_value=mock_creds,
            ),
            patch(
                "homebox_companion.core.llm_router.get_fallback_profile",
                return_value=None,
            ),
            patch(
                "homebox_companion.core.persistent_settings.SETTINGS_FILE"
            ) as mock_file,
            patch(
                "homebox_companion.core.persistent_settings.DATA_DIR"
            ) as mock_dir,
        ):
            mock_dir.mkdir = MagicMock()
            mock_file.write_text = MagicMock()

            # Get router (creates singleton)
            router1 = get_router()

            # Save settings (should invalidate)
            settings = PersistentSettings(
                llm_profiles=[
                    ModelProfile(
                        name="test",
                        model="gpt-5-mini",
                        status=ProfileStatus.PRIMARY,
                    )
                ]
            )
            save_settings(settings)

            # Get router again (should be new instance)
            router2 = get_router()

            assert router1 is not router2
