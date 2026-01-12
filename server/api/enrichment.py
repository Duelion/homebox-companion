"""Enrichment API endpoints.

Provides endpoints for:
- Enriching product data with AI-powered specification lookup
- Managing enrichment cache
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from homebox_companion.core.ai_config import load_ai_config, AIProvider
from homebox_companion.core.app_preferences import load_app_preferences
from homebox_companion.core.config import settings
from homebox_companion.providers import OllamaProvider, LiteLLMProvider
from homebox_companion.services.enrichment import EnrichmentService, EnrichmentResult
from homebox_companion.services.debug_logger import debug_log

from ..dependencies import require_auth, LLMConfig, get_configured_llm

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_auth)])

# Singleton enrichment service (lazy initialized)
_enrichment_service: EnrichmentService | None = None


def get_enrichment_service() -> EnrichmentService:
    """Get or create the enrichment service singleton."""
    global _enrichment_service
    if _enrichment_service is None:
        prefs = load_app_preferences()
        cache_ttl = prefs.enrichment_cache_ttl_hours * 3600  # Convert to seconds
        _enrichment_service = EnrichmentService(
            cache_dir=Path(settings.data_dir),
            cache_ttl=cache_ttl,
        )
    return _enrichment_service


def configure_search_provider(service: EnrichmentService) -> None:
    """Configure the search provider and custom retailer domains from app preferences."""
    prefs = load_app_preferences()
    service.configure_search_provider(
        provider_type=prefs.search_provider,
        tavily_api_key=prefs.search_tavily_api_key,
        google_api_key=prefs.search_google_api_key,
        google_engine_id=prefs.search_google_engine_id,
        searxng_url=prefs.search_searxng_url,
    )
    # Set custom retailer domains for price fetching
    if prefs.enrichment_retailer_domains:
        service.set_custom_retailer_domains(prefs.enrichment_retailer_domains)


def create_ai_provider(llm_config: LLMConfig) -> OllamaProvider | LiteLLMProvider:
    """Create an AI provider instance based on LLM configuration.

    Args:
        llm_config: LLM configuration with provider type, model, and API key.

    Returns:
        Provider instance with complete() method for text completion.
    """
    if llm_config.provider == "ollama":
        # Get Ollama URL from AI config
        ai_config = load_ai_config()
        return OllamaProvider(
            base_url=ai_config.ollama.url,
            model=llm_config.model,
            timeout=ai_config.ollama.timeout,
        )
    else:
        # OpenAI and Anthropic use LiteLLMProvider
        return LiteLLMProvider(
            api_key=llm_config.api_key,
            model=llm_config.model,
            provider_type=llm_config.provider,
            api_base=llm_config.api_base,
        )


# =============================================================================
# Request/Response Models
# =============================================================================


class EnrichRequest(BaseModel):
    """Request to enrich a product."""

    manufacturer: str = Field(default="", description="Product manufacturer")
    model_number: str = Field(default="", description="Product model number (required for enrichment)")
    product_name: str = Field(default="", description="Optional product name hint")


class EnrichResponse(BaseModel):
    """Response with enriched product data."""

    enriched: bool = Field(description="Whether enrichment was successful")
    source: str = Field(description="Source of data (ai_knowledge, cache, none)")
    name: str = Field(description="Full product name")
    description: str = Field(default="", description="Product description")
    features: list[str] = Field(default_factory=list, description="Product features")
    msrp: float | None = Field(default=None, description="Original MSRP if known")
    release_year: int | None = Field(default=None, description="Release year if known")
    category: str = Field(default="", description="Product category")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")
    formatted_description: str = Field(
        default="", description="Pre-formatted description for Homebox"
    )

    @classmethod
    def from_result(cls, result: EnrichmentResult, service: EnrichmentService) -> "EnrichResponse":
        """Create response from EnrichmentResult."""
        return cls(
            enriched=result.enriched,
            source=result.source,
            name=result.name,
            description=result.description,
            features=result.features,
            msrp=result.msrp,
            release_year=result.release_year,
            category=result.category,
            confidence=result.confidence,
            formatted_description=service.format_description(result) if result.enriched else "",
        )


class ClearCacheResponse(BaseModel):
    """Response from clearing the cache."""

    cleared_count: int = Field(description="Number of entries cleared")
    message: str = Field(description="Status message")


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/enrichment/lookup", response_model=EnrichResponse)
async def enrich_product(
    request: EnrichRequest,
    llm_config: Annotated[LLMConfig, Depends(get_configured_llm)],
) -> EnrichResponse:
    """
    Enrich product data with detailed specifications.

    Uses the configured AI provider to look up product details from its
    training knowledge. Results are cached to avoid repeated API calls.

    Requires enrichment to be enabled in settings.
    """
    debug_log("ENRICHMENT_API", "POST /enrichment/lookup called", {
        "manufacturer": request.manufacturer,
        "model_number": request.model_number,
        "product_name": request.product_name,
        "llm_provider": llm_config.provider,
        "llm_model": llm_config.model,
    })

    # Validate that we have at least a model number
    if not request.model_number or not request.model_number.strip():
        debug_log("ENRICHMENT_API", "No model number provided", level="WARNING")
        raise HTTPException(
            status_code=400,
            detail="Model number is required for enrichment.",
        )

    # Check if enrichment is enabled
    prefs = load_app_preferences()
    debug_log("ENRICHMENT_API", "Loaded app preferences", {
        "enrichment_enabled": prefs.enrichment_enabled,
        "enrichment_auto_enrich": prefs.enrichment_auto_enrich,
    })

    if not prefs.enrichment_enabled:
        debug_log("ENRICHMENT_API", "Enrichment disabled in preferences", level="WARNING")
        raise HTTPException(
            status_code=400,
            detail="Enrichment is disabled. Enable it in Settings.",
        )

    # Get the enrichment service
    service = get_enrichment_service()

    # Create and set the AI provider based on LLM config
    try:
        ai_provider = create_ai_provider(llm_config)
        debug_log("ENRICHMENT_API", f"Created AI provider: {type(ai_provider).__name__}", {
            "provider_type": llm_config.provider,
            "model": llm_config.model,
        })
        service.set_provider(ai_provider)
    except Exception as e:
        debug_log("ENRICHMENT_API", f"Failed to create AI provider: {e}", level="ERROR")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to create AI provider: {str(e)}",
        )

    # Configure search provider from preferences
    configure_search_provider(service)
    debug_log("ENRICHMENT_API", "Search provider configured", {
        "has_search_provider": service.has_search_provider,
        "provider": service.search_provider.provider_name if service.search_provider else "none",
    })

    # Perform enrichment
    try:
        result = await service.enrich(
            manufacturer=request.manufacturer,
            model_number=request.model_number,
            product_name=request.product_name,
        )
        debug_log("ENRICHMENT_API", "Enrichment complete", {
            "enriched": result.enriched,
            "source": result.source,
            "confidence": result.confidence,
        })
        return EnrichResponse.from_result(result, service)
    except Exception as e:
        logger.error(f"Enrichment failed: {e}")
        debug_log("ENRICHMENT_API", f"Enrichment failed: {e}", level="ERROR")
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")


@router.delete("/enrichment/cache", response_model=ClearCacheResponse)
async def clear_enrichment_cache() -> ClearCacheResponse:
    """Clear the enrichment cache."""
    service = get_enrichment_service()
    count = service.clear_cache()
    return ClearCacheResponse(
        cleared_count=count,
        message=f"Cleared {count} cached enrichment result(s)",
    )
