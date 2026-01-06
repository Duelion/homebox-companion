"""AI provider configuration API endpoints.

Provides endpoints for:
- Get current AI configuration
- Update AI configuration
- Reset to defaults
- Test provider connection
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, SecretStr

from homebox_companion.core.ai_config import (
    AIConfig,
    AIProvider,
    AnthropicConfig,
    LiteLLMConfig,
    OllamaConfig,
    OpenAIConfig,
    load_ai_config,
    reset_ai_config,
    save_ai_config,
)
from homebox_companion.providers.ollama import OllamaProvider

from ..dependencies import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


# =============================================================================
# Request/Response Models
# =============================================================================


class OllamaConfigInput(BaseModel):
    """Ollama configuration input from frontend."""

    enabled: bool = False
    url: str = "http://localhost:11434"
    model: str = "minicpm-v"
    timeout: int = 120


class OpenAIConfigInput(BaseModel):
    """OpenAI configuration input from frontend."""

    enabled: bool = False
    api_key: str | None = None  # Plain string from frontend
    model: str = "gpt-4o"
    max_tokens: int = 4096


class AnthropicConfigInput(BaseModel):
    """Anthropic configuration input from frontend."""

    enabled: bool = False
    api_key: str | None = None  # Plain string from frontend
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class LiteLLMConfigInput(BaseModel):
    """LiteLLM configuration input from frontend."""

    enabled: bool = True
    model: str = "gpt-4o"


class AIConfigInput(BaseModel):
    """AI configuration input from frontend."""

    active_provider: str = "litellm"
    fallback_to_cloud: bool = True
    fallback_provider: str = "litellm"
    ollama: OllamaConfigInput = Field(default_factory=OllamaConfigInput)
    openai: OpenAIConfigInput = Field(default_factory=OpenAIConfigInput)
    anthropic: AnthropicConfigInput = Field(default_factory=AnthropicConfigInput)
    litellm: LiteLLMConfigInput = Field(default_factory=LiteLLMConfigInput)


class AIConfigResponse(BaseModel):
    """AI configuration response (with masked API keys)."""

    active_provider: str
    fallback_to_cloud: bool
    fallback_provider: str
    ollama: dict[str, Any]
    openai: dict[str, Any]
    anthropic: dict[str, Any]
    litellm: dict[str, Any]
    providers: list[dict[str, Any]]  # List of available providers with status


class TestConnectionRequest(BaseModel):
    """Request to test a provider connection."""

    provider: str
    config: dict[str, Any] = Field(default_factory=dict)


class TestConnectionResponse(BaseModel):
    """Response from connection test."""

    success: bool
    provider: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Helper Functions
# =============================================================================


def get_provider_list(config: AIConfig) -> list[dict[str, Any]]:
    """Get list of providers with their status."""
    return [
        {
            "id": "ollama",
            "name": "Ollama (Local)",
            "description": "Run AI locally with Ollama",
            "enabled": config.ollama.enabled,
            "configured": config.is_provider_configured(AIProvider.OLLAMA),
            "requires_api_key": False,
        },
        {
            "id": "openai",
            "name": "OpenAI",
            "description": "GPT-4 Vision and other OpenAI models",
            "enabled": config.openai.enabled,
            "configured": config.is_provider_configured(AIProvider.OPENAI),
            "requires_api_key": True,
        },
        {
            "id": "anthropic",
            "name": "Anthropic (Claude)",
            "description": "Claude AI models",
            "enabled": config.anthropic.enabled,
            "configured": config.is_provider_configured(AIProvider.ANTHROPIC),
            "requires_api_key": True,
        },
        {
            "id": "litellm",
            "name": "Cloud (LiteLLM)",
            "description": "Default cloud provider via LiteLLM",
            "enabled": config.litellm.enabled,
            "configured": config.is_provider_configured(AIProvider.LITELLM),
            "requires_api_key": False,
        },
    ]


def mask_api_key(key: str | None) -> str | None:
    """Mask an API key for display."""
    if not key:
        return None
    if len(key) > 12:
        return f"{key[:8]}...{key[-4:]}"
    return "***"


def config_to_response(config: AIConfig) -> AIConfigResponse:
    """Convert AIConfig to response with masked keys."""
    ollama_dict = config.ollama.model_dump()
    openai_dict = config.openai.model_dump()
    anthropic_dict = config.anthropic.model_dump()
    litellm_dict = config.litellm.model_dump()

    # Mask API keys
    if openai_dict.get("api_key"):
        openai_dict["api_key"] = mask_api_key(
            config.openai.api_key.get_secret_value() if config.openai.api_key else None
        )
        openai_dict["has_api_key"] = True
    else:
        openai_dict["has_api_key"] = False

    if anthropic_dict.get("api_key"):
        anthropic_dict["api_key"] = mask_api_key(
            config.anthropic.api_key.get_secret_value() if config.anthropic.api_key else None
        )
        anthropic_dict["has_api_key"] = True
    else:
        anthropic_dict["has_api_key"] = False

    return AIConfigResponse(
        active_provider=config.active_provider.value,
        fallback_to_cloud=config.fallback_to_cloud,
        fallback_provider=config.fallback_provider.value,
        ollama=ollama_dict,
        openai=openai_dict,
        anthropic=anthropic_dict,
        litellm=litellm_dict,
        providers=get_provider_list(config),
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/settings/ai-config", response_model=AIConfigResponse)
async def get_ai_config() -> AIConfigResponse:
    """Get current AI configuration.

    Returns configuration with API keys masked for security.
    """
    config = load_ai_config()
    return config_to_response(config)


@router.put("/settings/ai-config", response_model=AIConfigResponse)
async def update_ai_config(input_config: AIConfigInput) -> AIConfigResponse:
    """Update AI configuration.

    Saves the configuration and optionally tests connection for Ollama.
    """
    logger.info(f"Updating AI config: active_provider={input_config.active_provider}")

    # Load existing config to preserve any keys not being updated
    existing = load_ai_config()

    # Build new config
    # Handle API keys - if empty string or "***" pattern, keep existing
    openai_key = input_config.openai.api_key
    if not openai_key or openai_key.startswith("***") or "..." in (openai_key or ""):
        openai_key = existing.openai.api_key.get_secret_value() if existing.openai.api_key else None

    anthropic_key = input_config.anthropic.api_key
    if not anthropic_key or anthropic_key.startswith("***") or "..." in (anthropic_key or ""):
        anthropic_key = existing.anthropic.api_key.get_secret_value() if existing.anthropic.api_key else None

    new_config = AIConfig(
        active_provider=AIProvider(input_config.active_provider),
        fallback_to_cloud=input_config.fallback_to_cloud,
        fallback_provider=AIProvider(input_config.fallback_provider),
        ollama=OllamaConfig(**input_config.ollama.model_dump()),
        openai=OpenAIConfig(
            enabled=input_config.openai.enabled,
            api_key=SecretStr(openai_key) if openai_key else None,
            model=input_config.openai.model,
            max_tokens=input_config.openai.max_tokens,
        ),
        anthropic=AnthropicConfig(
            enabled=input_config.anthropic.enabled,
            api_key=SecretStr(anthropic_key) if anthropic_key else None,
            model=input_config.anthropic.model,
            max_tokens=input_config.anthropic.max_tokens,
        ),
        litellm=LiteLLMConfig(**input_config.litellm.model_dump()),
    )

    save_ai_config(new_config)
    logger.info("AI config saved successfully")

    return config_to_response(new_config)


@router.delete("/settings/ai-config", response_model=AIConfigResponse)
async def delete_ai_config() -> AIConfigResponse:
    """Reset AI configuration to defaults."""
    logger.info("Resetting AI config to defaults")
    config = reset_ai_config()
    return config_to_response(config)


@router.post("/settings/ai-config/test", response_model=TestConnectionResponse)
async def test_provider_connection(request: TestConnectionRequest) -> TestConnectionResponse:
    """Test connection to an AI provider.

    For Ollama: Tests server connection and model availability.
    For OpenAI/Anthropic: Validates API key format (full test would incur cost).
    """
    provider = request.provider
    config = request.config

    if provider == "ollama":
        url = config.get("url", "http://localhost:11434")
        model = config.get("model", "minicpm-v")

        try:
            async with OllamaProvider(base_url=url, model=model) as ollama:
                result = await ollama.test_connection()

                if result.get("connected"):
                    model_available = result.get("model_available", False)
                    available_models = result.get("available_models", [])

                    if model_available:
                        return TestConnectionResponse(
                            success=True,
                            provider=provider,
                            message=f"Connected to Ollama. Model '{model}' is ready.",
                            details={
                                "url": url,
                                "model": model,
                                "available_models": available_models,
                            },
                        )
                    else:
                        return TestConnectionResponse(
                            success=True,
                            provider=provider,
                            message=f"Connected to Ollama, but model '{model}' not found. Available: {', '.join(available_models[:5])}",
                            details={
                                "url": url,
                                "model": model,
                                "model_available": False,
                                "available_models": available_models,
                            },
                        )
                else:
                    return TestConnectionResponse(
                        success=False,
                        provider=provider,
                        message=result.get("message", "Failed to connect to Ollama"),
                        details={"url": url},
                    )
        except Exception as e:
            logger.error(f"Ollama connection test failed: {e}")
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message=f"Connection failed: {str(e)}",
                details={"url": url, "error": str(e)},
            )

    elif provider == "openai":
        api_key = config.get("api_key")
        if not api_key or api_key.startswith("***"):
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message="API key is required",
                details={},
            )

        # Basic validation - check format
        if api_key.startswith("sk-") and len(api_key) > 20:
            return TestConnectionResponse(
                success=True,
                provider=provider,
                message="API key format is valid. Full validation would require an API call.",
                details={"model": config.get("model", "gpt-4o")},
            )
        else:
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message="Invalid API key format. OpenAI keys start with 'sk-'",
                details={},
            )

    elif provider == "anthropic":
        api_key = config.get("api_key")
        if not api_key or api_key.startswith("***"):
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message="API key is required",
                details={},
            )

        # Basic validation - check format
        if api_key.startswith("sk-ant-") and len(api_key) > 20:
            return TestConnectionResponse(
                success=True,
                provider=provider,
                message="API key format is valid. Full validation would require an API call.",
                details={"model": config.get("model", "claude-sonnet-4-20250514")},
            )
        else:
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message="Invalid API key format. Anthropic keys start with 'sk-ant-'",
                details={},
            )

    elif provider == "litellm":
        return TestConnectionResponse(
            success=True,
            provider=provider,
            message="LiteLLM (cloud) provider is always available.",
            details={"model": config.get("model", "gpt-4o")},
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
