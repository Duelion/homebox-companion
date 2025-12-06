"""Tests for custom OpenAI endpoint configuration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homebox_companion.ai.openai import _get_openai_client, chat_completion
from homebox_companion.core.config import Settings


def test_settings_accepts_openai_base_url() -> None:
    """Test that Settings can be initialized with custom base URL."""
    settings = Settings(
        openai_api_key="test-key",
        openai_base_url="http://localhost:1234/v1",
    )

    assert settings.openai_base_url == "http://localhost:1234/v1"


def test_settings_openai_base_url_defaults_to_none() -> None:
    """Test that openai_base_url defaults to None."""
    settings = Settings(openai_api_key="test-key")

    assert settings.openai_base_url is None


def test_get_openai_client_caches_by_key_and_url() -> None:
    """Test that client cache uses both api_key and base_url."""
    # Clear any existing cache
    from homebox_companion.ai import openai

    openai._client_cache.clear()

    # Create clients with same key but different URLs
    client1 = _get_openai_client("key1", None)
    client2 = _get_openai_client("key1", "http://custom.com")
    client3 = _get_openai_client("key1", None)  # Should reuse client1

    # client1 and client3 should be the same instance (same cache key)
    assert client1 is client3

    # client2 should be different (different base_url)
    assert client1 is not client2


@patch("homebox_companion.ai.openai.AsyncOpenAI")
def test_get_openai_client_passes_base_url_to_constructor(mock_openai_class: MagicMock) -> None:
    """Test that base_url is passed to AsyncOpenAI constructor."""
    from homebox_companion.ai import openai

    openai._client_cache.clear()

    _get_openai_client("test-key", "http://localhost:1234/v1")

    # Verify AsyncOpenAI was called with both api_key and base_url
    mock_openai_class.assert_called_once_with(
        api_key="test-key",
        base_url="http://localhost:1234/v1",
    )


@patch("homebox_companion.ai.openai.AsyncOpenAI")
def test_get_openai_client_omits_base_url_when_none(mock_openai_class: MagicMock) -> None:
    """Test that base_url is not passed when None."""
    from homebox_companion.ai import openai

    openai._client_cache.clear()

    _get_openai_client("test-key", None)

    # Verify AsyncOpenAI was called with only api_key
    mock_openai_class.assert_called_once_with(api_key="test-key")


@pytest.mark.asyncio
@patch("homebox_companion.ai.openai._get_openai_client")
async def test_chat_completion_uses_settings_base_url(mock_get_client: MagicMock) -> None:
    """Test that chat_completion uses base_url from settings when not provided."""
    # Mock the client and its response
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content='{"result": "test"}'))]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    mock_get_client.return_value = mock_client

    # Mock settings
    with patch("homebox_companion.ai.openai.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "test-model"
        mock_settings.openai_base_url = "http://custom.com/v1"

        messages = [{"role": "user", "content": "test"}]
        await chat_completion(messages)

        # Verify _get_openai_client was called with the settings base_url
        mock_get_client.assert_called_once_with("test-key", "http://custom.com/v1")


@pytest.mark.asyncio
@patch("homebox_companion.ai.openai._get_openai_client")
async def test_chat_completion_overrides_base_url(mock_get_client: MagicMock) -> None:
    """Test that chat_completion can override the base_url."""
    # Mock the client and its response
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content='{"result": "test"}'))]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    mock_get_client.return_value = mock_client

    # Mock settings
    with patch("homebox_companion.ai.openai.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "test-model"
        mock_settings.openai_base_url = "http://default.com/v1"

        messages = [{"role": "user", "content": "test"}]
        # Override with explicit base_url
        await chat_completion(messages, base_url="http://override.com/v1")

        # Verify _get_openai_client was called with the override base_url
        mock_get_client.assert_called_once_with("test-key", "http://override.com/v1")


@pytest.mark.asyncio
@patch("homebox_companion.ai.openai._get_openai_client")
async def test_chat_completion_uses_none_when_explicitly_passed(
    mock_get_client: MagicMock,
) -> None:
    """Test that chat_completion respects explicit None for base_url."""
    # Mock the client and its response
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content='{"result": "test"}'))]
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
    mock_get_client.return_value = mock_client

    # Mock settings with a base_url set
    with patch("homebox_companion.ai.openai.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "test-model"
        mock_settings.openai_base_url = "http://default.com/v1"

        messages = [{"role": "user", "content": "test"}]
        # Explicitly pass None to use official OpenAI endpoint
        await chat_completion(messages, base_url=None)

        # Verify _get_openai_client was called with None (explicit override)
        mock_get_client.assert_called_once_with("test-key", None)
