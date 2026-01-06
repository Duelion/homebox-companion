"""AI providers for Homebox Companion.

This module contains provider implementations for different AI backends:
- OllamaProvider: Native Ollama API client for local AI processing
"""

from __future__ import annotations

from .ollama import OllamaProvider

__all__ = ["OllamaProvider"]
