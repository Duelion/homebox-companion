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
    OllamaConfig,
    OpenAIConfig,
    load_ai_config,
    reset_ai_config,
    save_ai_config,
)
from homebox_companion.providers.ollama import OllamaProvider
from homebox_companion.providers.litellm_provider import LiteLLMProvider, LiteLLMProviderError
from homebox_companion.core.config import get_settings

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
    """OpenAI configuration input from frontend.

    Supports both direct OpenAI API and compatible endpoints via api_base.
    """

    enabled: bool = True  # Default enabled as primary cloud provider
    api_key: str | None = None  # Plain string from frontend
    api_base: str | None = None  # Custom API base URL for compatible endpoints
    model: str = "gpt-4o"
    max_tokens: int = 4096


class AnthropicConfigInput(BaseModel):
    """Anthropic configuration input from frontend."""

    enabled: bool = False
    api_key: str | None = None  # Plain string from frontend
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class AIConfigInput(BaseModel):
    """AI configuration input from frontend."""

    active_provider: str = "openai"
    fallback_to_cloud: bool = True
    fallback_provider: str = "openai"
    ollama: OllamaConfigInput = Field(default_factory=OllamaConfigInput)
    openai: OpenAIConfigInput = Field(default_factory=OpenAIConfigInput)
    anthropic: AnthropicConfigInput = Field(default_factory=AnthropicConfigInput)


class AIConfigResponse(BaseModel):
    """AI configuration response (with masked API keys)."""

    active_provider: str
    fallback_to_cloud: bool
    fallback_provider: str
    ollama: dict[str, Any]
    openai: dict[str, Any]
    anthropic: dict[str, Any]
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
            "description": "GPT-4 Vision and OpenAI-compatible endpoints",
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

    # Build OpenAI dict with proper API key handling
    openai_dict = {
        "enabled": config.openai.enabled,
        "model": config.openai.model,
        "api_base": config.openai.api_base,
        "max_tokens": config.openai.max_tokens,
    }
    if config.openai.api_key:
        openai_dict["api_key"] = mask_api_key(config.openai.api_key.get_secret_value())
        openai_dict["has_api_key"] = True
    else:
        openai_dict["api_key"] = None
        openai_dict["has_api_key"] = False

    # Build Anthropic dict with proper API key handling
    anthropic_dict = {
        "enabled": config.anthropic.enabled,
        "model": config.anthropic.model,
        "max_tokens": config.anthropic.max_tokens,
    }
    if config.anthropic.api_key:
        anthropic_dict["api_key"] = mask_api_key(config.anthropic.api_key.get_secret_value())
        anthropic_dict["has_api_key"] = True
    else:
        anthropic_dict["api_key"] = None
        anthropic_dict["has_api_key"] = False

    return AIConfigResponse(
        active_provider=config.active_provider.value,
        fallback_to_cloud=config.fallback_to_cloud,
        fallback_provider=config.fallback_provider.value,
        ollama=ollama_dict,
        openai=openai_dict,
        anthropic=anthropic_dict,
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
    logger.info(f"[AI_CONFIG] Starting save: active_provider={input_config.active_provider}")

    try:
        # Load existing config to preserve any keys not being updated
        logger.debug("[AI_CONFIG] Loading existing config...")
        existing = load_ai_config()
        logger.debug("[AI_CONFIG] Existing config loaded")
    except Exception as e:
        logger.error(f"[AI_CONFIG] Failed to load existing config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load existing config: {e}")

    # Build new config
    # Handle API keys - if empty string or "***" pattern, keep existing
    try:
        logger.debug("[AI_CONFIG] Processing API keys...")
        openai_key = input_config.openai.api_key
        if not openai_key or openai_key.startswith("***") or "..." in (openai_key or ""):
            openai_key = existing.openai.api_key.get_secret_value() if existing.openai.api_key else None

        anthropic_key = input_config.anthropic.api_key
        if not anthropic_key or anthropic_key.startswith("***") or "..." in (anthropic_key or ""):
            anthropic_key = existing.anthropic.api_key.get_secret_value() if existing.anthropic.api_key else None

        logger.debug(f"[AI_CONFIG] Keys processed: has_openai={openai_key is not None}, has_anthropic={anthropic_key is not None}")

        # Build sub-configs first (these are plain BaseModel, not BaseSettings)
        logger.debug("[AI_CONFIG] Building sub-configs...")
        ollama_cfg = OllamaConfig(**input_config.ollama.model_dump())
        openai_cfg = OpenAIConfig(
            enabled=input_config.openai.enabled,
            api_key=SecretStr(openai_key) if openai_key else None,
            api_base=input_config.openai.api_base,
            model=input_config.openai.model,
            max_tokens=input_config.openai.max_tokens,
        )
        anthropic_cfg = AnthropicConfig(
            enabled=input_config.anthropic.enabled,
            api_key=SecretStr(anthropic_key) if anthropic_key else None,
            model=input_config.anthropic.model,
            max_tokens=input_config.anthropic.max_tokens,
        )
        logger.debug("[AI_CONFIG] Sub-configs built")

        # Build main config - this is BaseSettings but we provide all values
        logger.debug("[AI_CONFIG] Building main AIConfig...")
        new_config = AIConfig(
            active_provider=AIProvider(input_config.active_provider),
            fallback_to_cloud=input_config.fallback_to_cloud,
            fallback_provider=AIProvider(input_config.fallback_provider),
            ollama=ollama_cfg,
            openai=openai_cfg,
            anthropic=anthropic_cfg,
        )
        logger.debug("[AI_CONFIG] Main config built successfully")
    except Exception as e:
        logger.error(f"[AI_CONFIG] Failed to build config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to build config: {e}")

    try:
        logger.debug("[AI_CONFIG] Saving config to file...")
        save_ai_config(new_config)
        logger.info("[AI_CONFIG] Config saved successfully")
    except Exception as e:
        logger.error(f"[AI_CONFIG] Failed to save config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save config: {e}")

    try:
        logger.debug("[AI_CONFIG] Building response...")
        response = config_to_response(new_config)
        logger.debug("[AI_CONFIG] Response built, returning...")
        return response
    except Exception as e:
        logger.error(f"[AI_CONFIG] Failed to create response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create response: {e}")


@router.delete("/settings/ai-config", response_model=AIConfigResponse)
async def delete_ai_config() -> AIConfigResponse:
    """Reset AI configuration to defaults."""
    logger.info("Resetting AI config to defaults")
    config = reset_ai_config()
    return config_to_response(config)


@router.post("/settings/ai-config/test", response_model=TestConnectionResponse)
async def test_provider_connection(request: TestConnectionRequest) -> TestConnectionResponse:
    """Test connection to an AI provider.

    For all providers: Makes a small API call to verify connectivity.
    """
    provider = request.provider
    config = request.config

    if provider == "ollama":
        url = config.get("url", "http://localhost:11434")
        model = config.get("model", "minicpm-v")
        timeout = config.get("timeout", 120)

        try:
            async with OllamaProvider(base_url=url, model=model, timeout=float(timeout)) as ollama:
                # Test with inference to verify the model actually responds
                result = await ollama.test_connection(test_inference=True)

                if result.get("connected"):
                    model_available = result.get("model_available", False)
                    available_models = result.get("available_models", [])

                    if not model_available:
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

                    # Check inference test results
                    inference_tested = result.get("inference_tested", False)
                    inference_success = result.get("inference_success", False)

                    if inference_tested and not inference_success:
                        inference_error = result.get("inference_error", "Unknown error")
                        return TestConnectionResponse(
                            success=False,
                            provider=provider,
                            message=f"Connected to Ollama, but model failed inference test: {inference_error}",
                            details={
                                "url": url,
                                "model": model,
                                "timeout": timeout,
                                "available_models": available_models,
                                "inference_error": inference_error,
                            },
                        )

                    return TestConnectionResponse(
                        success=True,
                        provider=provider,
                        message=f"Connected to Ollama. Model '{model}' is responding.",
                        details={
                            "url": url,
                            "model": model,
                            "timeout": timeout,
                            "available_models": available_models,
                            "response": result.get("inference_response", "OK"),
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
        model = config.get("model", "gpt-4o")
        api_key = config.get("api_key")
        api_base = config.get("api_base")
        use_stored_key = config.get("use_stored_key", False)

        # If use_stored_key is set, load the stored key/base from config
        if use_stored_key and (not api_key or api_key.startswith("***")):
            stored_config = load_ai_config()
            if stored_config.openai.api_key:
                api_key = stored_config.openai.api_key.get_secret_value()
            if not api_base and stored_config.openai.api_base:
                api_base = stored_config.openai.api_base

        # If still no api_key, try environment variable fallback
        if not api_key or api_key.startswith("***"):
            settings = get_settings()
            api_key = settings.effective_llm_api_key or None

        # Require either an API key or a custom api_base (self-hosted endpoints may not need auth)
        if not api_key and not api_base:
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message="API key is required. Enter an API key, set HBC_LLM_API_KEY environment variable, or configure a custom API base URL.",
                details={"model": model},
            )

        try:
            # Create provider with configured credentials
            openai_provider = LiteLLMProvider(
                api_key=api_key,
                model=model,
                provider_type="openai",
                timeout=30.0,  # Use shorter timeout for test
                api_base=api_base,
            )

            # Try a minimal completion to verify connectivity
            test_response = await openai_provider.complete(
                prompt="Respond with only the word 'OK'",
                system="You are a test assistant. Respond only with 'OK'.",
            )

            return TestConnectionResponse(
                success=True,
                provider=provider,
                message=f"Connected to OpenAI. Model '{model}' is responding.",
                details={
                    "model": model,
                    "api_base": api_base,
                    "response": test_response[:50] if test_response else "OK",
                },
            )

        except LiteLLMProviderError as e:
            error_msg = str(e)
            logger.error(f"OpenAI connection test failed: {error_msg}")
            # Provide helpful message for common errors
            if "AuthenticationError" in error_msg or "API key" in error_msg.lower():
                return TestConnectionResponse(
                    success=False,
                    provider=provider,
                    message="Authentication failed. Check your API key.",
                    details={"model": model, "api_base": api_base, "error": error_msg},
                )
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message=f"Connection failed: {error_msg}",
                details={"model": model, "api_base": api_base, "error": error_msg},
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"OpenAI connection test failed: {error_msg}")
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message=f"Connection failed: {error_msg}",
                details={"model": model, "api_base": api_base, "error": error_msg},
            )

    elif provider == "anthropic":
        model = config.get("model", "claude-sonnet-4-20250514")
        api_key = config.get("api_key")
        use_stored_key = config.get("use_stored_key", False)

        # If use_stored_key is set, load the stored key from config
        if use_stored_key and (not api_key or api_key.startswith("***")):
            stored_config = load_ai_config()
            if stored_config.anthropic.api_key:
                api_key = stored_config.anthropic.api_key.get_secret_value()

        if not api_key or api_key.startswith("***"):
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message="API key is required. Please enter an API key or save one first.",
                details={"model": model},
            )

        try:
            # Create provider with configured credentials
            anthropic_provider = LiteLLMProvider(
                api_key=api_key,
                model=model,
                provider_type="anthropic",
                timeout=30.0,  # Use shorter timeout for test
            )

            # Try a minimal completion to verify connectivity
            test_response = await anthropic_provider.complete(
                prompt="Respond with only the word 'OK'",
                system="You are a test assistant. Respond only with 'OK'.",
            )

            return TestConnectionResponse(
                success=True,
                provider=provider,
                message=f"Connected to Anthropic. Model '{model}' is responding.",
                details={
                    "model": model,
                    "response": test_response[:50] if test_response else "OK",
                },
            )

        except LiteLLMProviderError as e:
            error_msg = str(e)
            logger.error(f"Anthropic connection test failed: {error_msg}")
            # Provide helpful message for common errors
            if "AuthenticationError" in error_msg or "API key" in error_msg.lower():
                return TestConnectionResponse(
                    success=False,
                    provider=provider,
                    message="Authentication failed. Check your API key.",
                    details={"model": model, "error": error_msg},
                )
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message=f"Connection failed: {error_msg}",
                details={"model": model, "error": error_msg},
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Anthropic connection test failed: {error_msg}")
            return TestConnectionResponse(
                success=False,
                provider=provider,
                message=f"Connection failed: {error_msg}",
                details={"model": model, "error": error_msg},
            )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
