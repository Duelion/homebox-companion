"""AI providers for Homebox Companion.

This module contains provider implementations for different AI backends:
- OllamaProvider: Native Ollama API client for local AI processing
- LiteLLMProvider: LiteLLM wrapper for OpenAI, Anthropic, and other backends
"""

from __future__ import annotations

from .ollama import OllamaProvider
from .litellm_provider import LiteLLMProvider, LiteLLMProviderError

__all__ = ["OllamaProvider", "LiteLLMProvider", "LiteLLMProviderError"]
