"""LiteLLM-based provider for AI completions.

This module provides a provider that wraps LiteLLM for text completions,
supporting OpenAI, Anthropic, and other LiteLLM-compatible backends.

Usage:
    provider = LiteLLMProvider(
        api_key="sk-...",
        model="gpt-4o-mini",
        provider_type="openai"
    )
    response = await provider.complete("What is 2+2?")
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

# Import litellm lazily to avoid startup delays
_litellm = None


def _get_litellm():
    """Get litellm module, importing lazily."""
    global _litellm
    if _litellm is None:
        import litellm as lm
        _litellm = lm
    return _litellm


class LiteLLMProviderError(Exception):
    """Exception raised for LiteLLM provider errors."""
    pass


class LiteLLMProvider:
    """Provider that wraps LiteLLM for AI completions.

    Supports multiple backends through LiteLLM:
    - OpenAI (gpt-4o-mini, gpt-4o, etc.)
    - Anthropic (claude-3-sonnet, claude-3-opus, etc.)
    - Custom LiteLLM proxy endpoints
    """

    def __init__(
        self,
        api_key: str | None,
        model: str,
        provider_type: str = "openai",
        timeout: float = 120.0,
        api_base: str | None = None,
    ):
        """Initialize the LiteLLM provider.

        Args:
            api_key: API key for the provider (may be None for some backends)
            model: Model name to use
            provider_type: Provider type (openai, anthropic, litellm)
            timeout: Request timeout in seconds
            api_base: Optional custom API base URL (for self-hosted endpoints)
        """
        self.api_key = api_key
        self.model = model
        self.provider_type = provider_type
        self.timeout = timeout
        self.api_base = api_base

    def _get_litellm_model(self) -> str:
        """Get the model name formatted for LiteLLM.

        For Anthropic, we need to prefix the model name.
        """
        if self.provider_type == "anthropic":
            if not self.model.startswith("anthropic/"):
                return f"anthropic/{self.model}"
        return self.model

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        format_json: bool = False,
    ) -> str:
        """Generate a text completion.

        Args:
            prompt: The prompt text
            system: Optional system prompt
            format_json: If True, request JSON output format

        Returns:
            Generated text

        Raises:
            LiteLLMProviderError: If completion fails
        """
        litellm = _get_litellm()

        messages: list[dict[str, str]] = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self._get_litellm_model(),
            "messages": messages,
            "timeout": self.timeout,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.api_base:
            kwargs["api_base"] = self.api_base

        if format_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            logger.info(f"LiteLLM completion starting: model={self.model}, provider={self.provider_type}")

            # Run synchronous litellm.completion in a thread pool
            response = await asyncio.to_thread(
                litellm.completion,
                **kwargs
            )

            # Extract the response text
            content = response.choices[0].message.content
            logger.info(f"LiteLLM completion successful: {len(content) if content else 0} chars")
            logger.debug(f"LiteLLM response preview: {(content or '')[:200]}")
            return content or ""

        except Exception as e:
            error_msg = str(e)
            logger.error(f"LiteLLM completion failed: {error_msg}")
            raise LiteLLMProviderError(f"Completion failed: {error_msg}") from e

    async def is_available(self) -> bool:
        """Check if the provider is configured and likely to work.

        Returns:
            True if the provider appears to be configured.
        """
        # For API-key based providers, check if key is set or api_base is configured
        if self.provider_type in ("openai", "anthropic"):
            return bool(self.api_key) or bool(self.api_base)
        # For litellm proxy, assume it's available if model is set or api_base is configured
        return bool(self.model) or bool(self.api_base)
