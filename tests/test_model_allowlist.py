"""Tests for the model allowlist and capability checking."""

from __future__ import annotations

import pytest

from homebox_companion.ai.model_allowlist import (
    MODEL_ALLOWLIST,
    ModelCapabilities,
    extract_base_model,
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


class TestModelAllowlist:
    """Tests for the MODEL_ALLOWLIST constant."""

    def test_allowlist_is_not_empty(self) -> None:
        """The allowlist should contain at least one model."""
        assert len(MODEL_ALLOWLIST) > 0

    def test_gpt5_mini_is_allowlisted(self) -> None:
        """gpt-5-mini should be in the allowlist (project default)."""
        assert "gpt-5-mini" in MODEL_ALLOWLIST

    def test_allowlisted_models_have_correct_type(self) -> None:
        """All allowlisted entries should be ModelCapabilities."""
        for name, caps in MODEL_ALLOWLIST.items():
            assert isinstance(name, str), f"Key {name} should be a string"
            assert isinstance(caps, ModelCapabilities), (
                f"Value for {name} should be ModelCapabilities"
            )


class TestGetModelCapabilities:
    """Tests for the get_model_capabilities function."""

    def test_allowlisted_model_returns_capabilities(self) -> None:
        """Allowlisted models should return their capabilities."""
        caps = get_model_capabilities("gpt-5-mini")
        assert caps is not None
        assert caps.model == "gpt-5-mini"
        assert caps.vision is True
        assert caps.multi_image is True
        assert caps.json_mode is True

    def test_provider_prefixed_model_uses_base_capabilities(self) -> None:
        """Provider-prefixed models should resolve to base allowlist capabilities."""
        caps = get_model_capabilities("openrouter/openai/gpt-5-mini")
        assert caps is not None
        assert caps.model == "gpt-5-mini"

    def test_provider_prefixed_model_is_not_allowlisted_without_base_match(self) -> None:
        """Provider-prefixed models should fail if the base model isn't allowlisted."""
        caps = get_model_capabilities("openrouter/anthropic/claude-3.5-sonnet")
        assert caps is None

    def test_unknown_model_returns_none_by_default(self) -> None:
        """Unknown models should return None when allow_unsafe=False."""
        caps = get_model_capabilities("unknown-model-xyz")
        assert caps is None

    def test_unknown_model_with_unsafe_returns_conservative_caps(self) -> None:
        """Unknown models should return conservative caps when allow_unsafe=True."""
        caps = get_model_capabilities("unknown-model-xyz", allow_unsafe=True)
        assert caps is not None
        assert caps.model == "unknown-model-xyz"
        # Conservative defaults
        assert caps.vision is False
        assert caps.multi_image is False
        assert caps.json_mode is False


class TestExtractBaseModel:
    """Tests for extract_base_model()."""

    def test_plain_model(self) -> None:
        assert extract_base_model("gpt-5-mini") == "gpt-5-mini"

    def test_openrouter_prefix(self) -> None:
        assert extract_base_model("openrouter/openai/gpt-5-mini") == "gpt-5-mini"
        assert (
            extract_base_model("openrouter/anthropic/claude-3.5-sonnet") == "claude-3.5-sonnet"
        )

    def test_trims_whitespace(self) -> None:
        assert extract_base_model("  openrouter/openai/gpt-5-mini  ") == "gpt-5-mini"

    def test_empty_string(self) -> None:
        assert extract_base_model("") == ""
        assert extract_base_model("   ") == ""

    def test_provider_dot_prefix(self) -> None:
        assert extract_base_model("bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0") == (
            "claude-3-5-sonnet-20241022-v2:0"
        )

    def test_empty_model_returns_none(self) -> None:
        """Empty string model should return None."""
        assert get_model_capabilities("") is None
        assert get_model_capabilities("   ") is None

    def test_none_model_returns_none(self) -> None:
        """None model should return None."""
        assert get_model_capabilities(None) is None  # type: ignore[arg-type]

    def test_whitespace_is_stripped(self) -> None:
        """Model names with whitespace should be normalized."""
        caps = get_model_capabilities("  gpt-5-mini  ")
        # Should not match because we don't do fuzzy matching
        # The model name must match exactly after stripping
        # Note: MODEL_ALLOWLIST has "gpt-5-mini", not "  gpt-5-mini  "
        # The function strips whitespace before lookup
        assert caps is not None
        assert caps.model == "gpt-5-mini"

    def test_case_sensitive(self) -> None:
        """Model lookup should be case-sensitive."""
        # "gpt-5-mini" is allowlisted, but "GPT-5-MINI" is not
        caps_lower = get_model_capabilities("gpt-5-mini")
        caps_upper = get_model_capabilities("GPT-5-MINI")

        assert caps_lower is not None
        assert caps_upper is None  # Different case = different model

