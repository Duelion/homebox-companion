"""Tests for model capability checking via LiteLLM."""

from __future__ import annotations

import pytest

from homebox_companion.ai.model_capabilities import (
    ModelCapabilities,
    get_model_capabilities,
)


class TestModelCapabilities:
    """Tests for the ModelCapabilities dataclass."""

    def test_defaults_are_false(self) -> None:
        """Default capabilities should be False (conservative)."""
        caps = ModelCapabilities("test-model")
        assert caps.vision is False
        assert caps.multi_image is False
        assert caps.json_mode is False

    def test_custom_capabilities(self) -> None:
        """Custom capabilities should be settable."""
        caps = ModelCapabilities(
            "custom-model",
            vision=True,
            multi_image=True,
            json_mode=True,
        )
        assert caps.vision is True
        assert caps.multi_image is True
        assert caps.json_mode is True

    def test_frozen_dataclass(self) -> None:
        """ModelCapabilities should be immutable (frozen)."""
        caps = ModelCapabilities("test-model", vision=True)
        with pytest.raises(AttributeError):
            caps.vision = False  # type: ignore[misc]


class TestGetModelCapabilities:
    """Tests for the get_model_capabilities function."""

    def test_vision_model_gpt4o(self) -> None:
        """GPT-4o should be recognized as vision-capable."""
        caps = get_model_capabilities("gpt-4o")
        assert caps.model == "gpt-4o"
        assert caps.vision is True
        assert caps.multi_image is True  # Assumes all vision models support multi-image
        assert caps.json_mode is True

    def test_vision_model_with_provider_prefix(self) -> None:
        """Provider-prefixed models should work (e.g., OpenRouter)."""
        caps = get_model_capabilities("openrouter/openai/gpt-4o")
        assert caps.model == "openrouter/openai/gpt-4o"
        assert caps.vision is True
        assert caps.multi_image is True

    def test_non_vision_model(self) -> None:
        """Non-vision models should be recognized correctly."""
        caps = get_model_capabilities("gpt-3.5-turbo")
        assert caps.model == "gpt-3.5-turbo"
        assert caps.vision is False
        assert caps.multi_image is False

    def test_claude_vision_model(self) -> None:
        """Claude 3+ models should be recognized as vision-capable."""
        caps = get_model_capabilities("claude-3-5-sonnet-20241022")
        assert caps.model == "claude-3-5-sonnet-20241022"
        assert caps.vision is True
        assert caps.multi_image is True

    def test_gemini_vision_model(self) -> None:
        """Gemini models should be recognized as vision-capable."""
        caps = get_model_capabilities("gemini-2.0-flash")
        assert caps.model == "gemini-2.0-flash"
        assert caps.vision is True
        assert caps.multi_image is True

    def test_unknown_model_returns_conservative_capabilities(self) -> None:
        """Unknown models should return conservative (False) capabilities."""
        caps = get_model_capabilities("unknown-model-xyz")
        assert caps.model == "unknown-model-xyz"
        # LiteLLM will return False for capabilities it doesn't recognize
        assert caps.vision is False
        assert caps.multi_image is False
        assert caps.json_mode is False

