"""Ollama API endpoints for local AI management.

Provides endpoints for:
- Status: Check Ollama connection and model availability
- Models: List, pull, and manage models
- GPU: Detect and report GPU information
- Test: Test Ollama connection with custom URL
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from homebox_companion import settings
from homebox_companion.providers.ollama import OllamaProvider
from homebox_companion.services.gpu_detector import detect_gpu
from homebox_companion.services.ollama_manager import (
    OllamaManager,
    OllamaMode,
    get_ollama_manager,
)

router = APIRouter(prefix="/ollama")


# =============================================================================
# Request/Response Models
# =============================================================================


class OllamaTestRequest(BaseModel):
    """Request to test Ollama connection."""

    url: str | None = Field(None, description="Ollama URL to test (default: configured)")
    model: str | None = Field(None, description="Model to check for")


class OllamaTestResponse(BaseModel):
    """Response from Ollama connection test."""

    status: str
    connected: bool
    url: str
    model: str | None = None
    model_available: bool = False
    available_models: list[str] = []
    message: str | None = None


class ModelPullRequest(BaseModel):
    """Request to pull a model."""

    model: str = Field(..., description="Model name to pull")


class ModelPullResponse(BaseModel):
    """Response from model pull request."""

    status: str
    model: str
    error: str | None = None


class OllamaStatusResponse(BaseModel):
    """Full Ollama status response."""

    mode: str
    connected: bool
    url: str
    current_model: str
    model_ready: bool
    available_models: list[str]
    gpu: dict[str, Any] | None
    internal_running: bool
    error: str | None


class GPUInfoResponse(BaseModel):
    """GPU detection response."""

    detected: bool
    vendor: str
    name: str
    vram_mb: int
    vram_gb: float
    driver_version: str
    cuda_version: str
    compute_capability: str
    recommended_model: str
    supports_vision_models: bool
    detection_method: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=OllamaStatusResponse)
async def get_ollama_status() -> OllamaStatusResponse:
    """Get current Ollama status.

    Returns connection status, model availability, and GPU information.
    """
    manager = await get_ollama_manager()
    status = await manager.get_status()
    return OllamaStatusResponse(**status.to_dict())


@router.post("/test", response_model=OllamaTestResponse)
async def test_ollama_connection(request: OllamaTestRequest) -> OllamaTestResponse:
    """Test connection to an Ollama server.

    Can test both the configured server and custom URLs.
    """
    url = request.url or settings.ollama_url
    model = request.model or settings.ollama_model

    provider = OllamaProvider(base_url=url, model=model)
    try:
        result = await provider.test_connection()
        return OllamaTestResponse(
            status=result.get("status", "unknown"),
            connected=result.get("connected", False),
            url=url,
            model=model,
            model_available=result.get("model_available", False),
            available_models=result.get("available_models", []),
            message=result.get("message"),
        )
    finally:
        await provider.close()


@router.get("/models", response_model=list[dict[str, Any]])
async def list_models() -> list[dict[str, Any]]:
    """List all available Ollama models."""
    manager = await get_ollama_manager()

    if manager.mode == OllamaMode.DISABLED:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not enabled. Set HBC_USE_OLLAMA=true to enable.",
        )

    if not manager.provider:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not initialized",
        )

    return await manager.list_models()


@router.post("/pull", response_model=ModelPullResponse)
async def pull_model(request: ModelPullRequest) -> ModelPullResponse:
    """Pull a model from Ollama registry.

    This may take several minutes for large models.
    """
    manager = await get_ollama_manager()

    if manager.mode == OllamaMode.DISABLED:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not enabled. Set HBC_USE_OLLAMA=true to enable.",
        )

    result = await manager.pull_model(request.model)
    return ModelPullResponse(
        status=result.get("status", "unknown"),
        model=request.model,
        error=result.get("error"),
    )


@router.get("/gpu", response_model=GPUInfoResponse)
async def get_gpu_info() -> GPUInfoResponse:
    """Detect and return GPU information.

    Detects NVIDIA, AMD, Intel, and Apple Silicon GPUs.
    """
    gpu_info = detect_gpu()
    return GPUInfoResponse(**gpu_info.to_dict())


@router.get("/recommended-model")
async def get_recommended_model() -> dict[str, Any]:
    """Get recommended Ollama model based on detected GPU.

    Returns the model that best matches the available GPU VRAM.
    """
    gpu_info = detect_gpu()
    return {
        "recommended_model": gpu_info.recommended_model,
        "gpu_detected": gpu_info.detected,
        "gpu_name": gpu_info.name,
        "vram_gb": gpu_info.vram_gb,
        "supports_vision": gpu_info.supports_vision_models,
        "all_recommendations": {
            "48gb+": "llama3.2-vision:90b",
            "8gb+": "llama3.2-vision:11b",
            "6gb+": "minicpm-v",
            "4gb+": "granite3.2-vision",
            "3gb+": "moondream",
            "cpu": "moondream",
        },
    }


@router.get("/config")
async def get_ollama_config() -> dict[str, Any]:
    """Get current Ollama configuration from settings."""
    return {
        "use_ollama": settings.use_ollama,
        "ollama_internal": settings.ollama_internal,
        "ollama_url": settings.ollama_url,
        "ollama_model": settings.ollama_model,
        "fallback_to_cloud": settings.fallback_to_cloud,
    }
