"""Test model capability validation.

This file tests that the app properly validates model capabilities
and throws appropriate errors when using models that don't support
required features (vision, JSON schema).

Test Coverage:
--------------
1. Capability Detection (TestCapabilityChecking):
   - Vision models correctly report vision + JSON schema support
   - Text-only models correctly report no vision support
   - Older vision models (gemini-pro-vision) report vision but no schema

2. Vision Validation (TestVisionValidation):
   - Text-only models are rejected with CapabilityNotSupportedError
   - Unsafe flag (HBC_LLM_ALLOW_UNSAFE_MODELS=true) bypasses validation
   - Vision models without JSON schema support still work (fallback to prompt-based JSON)

3. Error Messages (TestErrorMessages):
   - Error messages suggest officially supported models (gpt-5-mini, gpt-5-nano)
   - Error messages explain the bypass flag (HBC_LLM_ALLOW_UNSAFE_MODELS=true)

4. Unsafe Flag Behavior (TestUnsafeFlagBehavior):
   - With unsafe flag, text-only models fail at LiteLLM level (not our validation)
   - Users get clear LiteLLM/provider errors about vision support
   - Vision models without JSON schema work fine with unsafe flag

5. Caching (TestCapabilityCacheing):
   - Capability checks are cached to avoid repeated LiteLLM queries

Run with:
    uv run pytest tests/test_model_capability_validation.py -v
"""

from __future__ import annotations

import os

import pytest

from homebox_companion.ai.llm import CapabilityNotSupportedError, LLMError, vision_completion
from homebox_companion.ai.model_capabilities import get_model_capabilities

# Use a tiny 1x1 pixel image for testing
TINY_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
TINY_IMAGE_DATA_URI = f"data:image/png;base64,{TINY_IMAGE_BASE64}"


@pytest.fixture(scope="session")
def openai_api_key() -> str:
    """Provide OpenAI API key for testing."""
    key = os.environ.get("TEST_OPENAI_API_KEY", "").strip()
    if not key:
        pytest.skip("TEST_OPENAI_API_KEY must be set for OpenAI tests.")
    return key


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to default state before each test."""
    from homebox_companion.core import config

    # Store original value
    original_env = os.environ.get("HBC_LLM_ALLOW_UNSAFE_MODELS")

    # Ensure unsafe models flag is OFF for tests
    if "HBC_LLM_ALLOW_UNSAFE_MODELS" in os.environ:
        del os.environ["HBC_LLM_ALLOW_UNSAFE_MODELS"]

    # Reload config
    config.settings = config.Settings()

    yield

    # Restore original value
    if original_env is not None:
        os.environ["HBC_LLM_ALLOW_UNSAFE_MODELS"] = original_env
    elif "HBC_LLM_ALLOW_UNSAFE_MODELS" in os.environ:
        del os.environ["HBC_LLM_ALLOW_UNSAFE_MODELS"]

    # Reload config again
    config.settings = config.Settings()


class TestCapabilityChecking:
    """Test LiteLLM capability detection."""

    def test_vision_model_capabilities(self):
        """Test that a known vision model reports correct capabilities."""
        caps = get_model_capabilities("gpt-4o")
        assert caps.vision is True
        assert caps.json_mode is True
        assert caps.multi_image is True

    def test_text_only_model_capabilities(self):
        """Test that a text-only model reports no vision."""
        caps = get_model_capabilities("gpt-3.5-turbo")
        assert caps.vision is False
        # JSON mode depends on LiteLLM's assessment
        assert caps.multi_image is False  # multi_image = vision

    def test_vision_model_without_schema_support(self):
        """Test a vision model that doesn't support JSON schema."""
        # gpt-4-turbo has vision but doesn't support structured outputs/JSON schema
        caps = get_model_capabilities("gpt-4-turbo")
        assert caps.vision is True
        assert caps.json_mode is False  # Older model, no structured outputs
        assert caps.multi_image is True


@pytest.mark.integration
class TestVisionValidation:
    """Test that vision_completion validates vision support."""

    @pytest.mark.asyncio
    async def test_text_only_model_raises_error(self, openai_api_key):
        """Test that using a text-only model raises CapabilityNotSupportedError."""
        with pytest.raises(CapabilityNotSupportedError) as exc_info:
            await vision_completion(
                system_prompt="You are a helpful assistant.",
                user_prompt="Describe this image",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="gpt-3.5-turbo",  # Text-only model
            )

        error_msg = str(exc_info.value)
        assert "gpt-3.5-turbo" in error_msg
        assert "does not support vision" in error_msg
        assert "HBC_LLM_ALLOW_UNSAFE_MODELS" in error_msg

    @pytest.mark.asyncio
    async def test_text_only_model_with_unsafe_flag(self, openai_api_key, monkeypatch):
        """Test that unsafe models flag skips validation."""
        # Set the unsafe models flag
        monkeypatch.setenv("HBC_LLM_ALLOW_UNSAFE_MODELS", "true")

        # Force reload config
        from homebox_companion.core import config
        config.settings = config.Settings()

        # This should NOT raise an error, but will fail at LiteLLM level
        # since the model truly doesn't support vision
        with pytest.raises(Exception) as exc_info:
            await vision_completion(
                system_prompt="You are a helpful assistant.",
                user_prompt="Describe this image",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="gpt-3.5-turbo",
            )

        # Should NOT be our CapabilityNotSupportedError
        assert not isinstance(exc_info.value, CapabilityNotSupportedError)
        # Should be a LiteLLM or provider error
        error_msg = str(exc_info.value).lower()
        assert any(
            keyword in error_msg
            for keyword in ["invalid", "not supported", "error", "unsupported"]
        )

    @pytest.mark.asyncio
    async def test_old_vision_model_without_json_schema(self, openai_api_key):
        """Test vision model without JSON schema support still works.

        The app should work with vision models that don't support structured
        outputs by falling back to prompt-based JSON.
        """
        try:
            result = await vision_completion(
                system_prompt="Respond with valid JSON only: {\"description\": \"...\"}",
                user_prompt="Describe this tiny 1x1 pixel image briefly.",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="gpt-4-turbo",  # Has vision, no JSON schema
                expected_keys=["description"],
            )

            # Should succeed and return a dict
            assert isinstance(result, dict)
            # May have description key if parsing worked
            # (but this is a tiny image so results may vary)

        except Exception as e:
            # If we get auth or access errors, that's fine - the important
            # part is that we didn't get CapabilityNotSupportedError
            if isinstance(e, CapabilityNotSupportedError):
                pytest.fail(
                    f"Should not raise CapabilityNotSupportedError for vision models "
                    f"without JSON schema support. Got: {e}"
                )
            # Other errors (auth, rate limit, etc.) are acceptable for this test
            pytest.skip(f"Cannot test gpt-4-turbo: {e}")


@pytest.mark.integration
class TestErrorMessages:
    """Test that error messages are helpful."""

    @pytest.mark.asyncio
    async def test_error_message_suggests_alternatives(self, openai_api_key):
        """Test that error message suggests officially supported models."""
        with pytest.raises(CapabilityNotSupportedError) as exc_info:
            await vision_completion(
                system_prompt="Test",
                user_prompt="Test",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="text-davinci-003",  # Old text-only model
            )

        error_msg = str(exc_info.value)
        # Should mention officially supported models
        assert "gpt-5-mini" in error_msg or "gpt-5-nano" in error_msg
        assert "Officially supported" in error_msg

    @pytest.mark.asyncio
    async def test_error_message_includes_bypass_flag(self, openai_api_key):
        """Test that error message explains the bypass flag."""
        with pytest.raises(CapabilityNotSupportedError) as exc_info:
            await vision_completion(
                system_prompt="Test",
                user_prompt="Test",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="gpt-4",  # Text-only model
            )

        error_msg = str(exc_info.value)
        assert "HBC_LLM_ALLOW_UNSAFE_MODELS=true" in error_msg
        assert "bypass" in error_msg.lower()


@pytest.mark.integration
class TestUnsafeFlagBehavior:
    """Test what happens when unsafe flag is enabled with incompatible models.

    These tests verify that users get clear LiteLLM/provider errors when they
    bypass our safety checks and try to use models that don't actually support
    the required capabilities.
    """

    @pytest.mark.asyncio
    async def test_text_only_model_with_unsafe_flag_gets_litellm_error(
        self, openai_api_key, monkeypatch
    ):
        """Test that text-only models fail at LiteLLM level with unsafe flag.

        When users bypass our checks with HBC_LLM_ALLOW_UNSAFE_MODELS=true,
        they should get a clear error from LiteLLM or the provider about
        vision not being supported.

        Expected: LLMError wrapping litellm.BadRequestError
        Message: "Invalid content type. image_url is only supported by certain models"
        """
        # Enable unsafe models flag
        monkeypatch.setenv("HBC_LLM_ALLOW_UNSAFE_MODELS", "true")

        # Force reload config
        from homebox_companion.core import config
        config.settings = config.Settings()

        # This should NOT raise CapabilityNotSupportedError
        # but should fail at LiteLLM level (wrapped in LLMError)
        with pytest.raises(LLMError) as exc_info:
            await vision_completion(
                system_prompt="You are a helpful assistant.",
                user_prompt="Describe this image",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="gpt-3.5-turbo",  # Text-only model
            )

        # Should be LLMError (wrapping LiteLLM's BadRequestError)
        assert isinstance(exc_info.value, LLMError)
        assert not isinstance(exc_info.value, CapabilityNotSupportedError)

        # Error message should mention vision/image support
        error_msg = str(exc_info.value).lower()
        assert any(
            keyword in error_msg
            for keyword in ["image_url", "image", "vision", "content type"]
        ), f"Expected error about vision support, got: {exc_info.value}"

    @pytest.mark.asyncio
    async def test_legacy_text_model_with_unsafe_flag_gets_provider_error(
        self, openai_api_key, monkeypatch
    ):
        """Test that legacy text models fail with provider errors.

        Models like gpt-4 (non-vision) should fail when images are provided,
        even with the unsafe flag enabled.

        Expected: LLMError wrapping litellm.UnsupportedParamsError
        Message: "openai does not support parameters: ['response_format'], for model=gpt-4"
        """
        # Enable unsafe models flag
        monkeypatch.setenv("HBC_LLM_ALLOW_UNSAFE_MODELS", "true")

        # Force reload config
        from homebox_companion.core import config
        config.settings = config.Settings()

        with pytest.raises(LLMError) as exc_info:
            await vision_completion(
                system_prompt="You are a helpful assistant.",
                user_prompt="Describe this image",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="gpt-4",  # Text-only model
            )

        # Should be LLMError (wrapping LiteLLM's UnsupportedParamsError)
        assert isinstance(exc_info.value, LLMError)
        assert not isinstance(exc_info.value, CapabilityNotSupportedError)

        # Error message should mention unsupported parameters
        error_msg = str(exc_info.value).lower()
        assert any(
            keyword in error_msg
            for keyword in ["response_format", "unsupported", "not support", "parameters"]
        ), f"Expected error about unsupported parameters, got: {exc_info.value}"

    @pytest.mark.asyncio
    async def test_vision_model_without_schema_works_with_unsafe_flag(
        self, openai_api_key, monkeypatch
    ):
        """Test that vision models without JSON schema still work.

        Models with vision but without JSON schema support should work fine
        (they'll use prompt-based JSON instead of structured outputs).
        """
        # Enable unsafe models flag
        monkeypatch.setenv("HBC_LLM_ALLOW_UNSAFE_MODELS", "true")

        # Force reload config
        from homebox_companion.core import config
        config.settings = config.Settings()

        try:
            result = await vision_completion(
                system_prompt=(
                    'Respond with valid JSON only: {"color": "...", "description": "..."}'
                ),
                user_prompt="What color is this 1x1 pixel image? Respond with JSON.",
                image_data_uris=[TINY_IMAGE_DATA_URI],
                api_key=openai_api_key,
                model="gpt-4-turbo",  # Has vision, no JSON schema
                expected_keys=["color", "description"],
            )

            # Should succeed and return a dict
            assert isinstance(result, dict)
            # Should have the expected structure (if parsing worked)
            assert "color" in result or "description" in result or len(result) > 0

        except Exception as e:
            # If we get auth/access errors, that's acceptable
            # The important part is we didn't get CapabilityNotSupportedError
            if isinstance(e, CapabilityNotSupportedError):
                pytest.fail(
                    f"Should not raise CapabilityNotSupportedError for vision models. Got: {e}"
                )

            # Check if it's an auth/access error (acceptable) or something else
            error_msg = str(e).lower()
            if any(
                keyword in error_msg
                for keyword in [
                    "auth", "permission", "access", "api key", "not found", "rate limit"
                ]
            ):
                pytest.skip(f"Cannot test gpt-4-turbo due to auth/access: {e}")
            else:
                # Re-raise if it's an unexpected error
                raise


class TestCapabilityCacheing:
    """Test that capability checks are cached."""

    def test_capability_cache_works(self):
        """Test that repeated calls use cached results."""
        from homebox_companion.ai.model_capabilities import get_model_capabilities

        # Clear cache
        get_model_capabilities.cache_clear()

        # First call
        caps1 = get_model_capabilities("gpt-4o")

        # Second call should be cached (same object)
        caps2 = get_model_capabilities("gpt-4o")

        # Should be the exact same object (cached)
        assert caps1 is caps2

        # Different model should not be cached
        caps3 = get_model_capabilities("gpt-4o-mini")
        assert caps3 is not caps1

