"""App preferences API endpoints.

Provides endpoints for:
- Get current app preferences
- Update app preferences
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from homebox_companion.core.app_preferences import (
    AppPreferences,
    load_app_preferences,
    save_app_preferences,
    get_effective_homebox_url,
    get_effective_image_quality,
)

from ..dependencies import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


# =============================================================================
# Request/Response Models
# =============================================================================


class AppPreferencesInput(BaseModel):
    """App preferences input from frontend."""

    homebox_url_override: str | None = None
    image_quality_override: str | None = None
    duplicate_detection_enabled: bool = True
    enrichment_enabled: bool = False
    enrichment_auto_enrich: bool = False
    enrichment_cache_ttl_hours: int = 24
    # Web search settings
    search_provider: str = "none"
    search_tavily_api_key: str | None = None
    search_google_api_key: str | None = None
    search_google_engine_id: str | None = None
    search_searxng_url: str | None = None


class AppPreferencesResponse(BaseModel):
    """App preferences response with effective values."""

    # Raw preference values
    homebox_url_override: str | None
    image_quality_override: str | None
    duplicate_detection_enabled: bool

    # Enrichment settings
    enrichment_enabled: bool
    enrichment_auto_enrich: bool
    enrichment_cache_ttl_hours: int

    # Web search settings
    search_provider: str
    search_tavily_api_key: str | None
    search_google_api_key: str | None
    search_google_engine_id: str | None
    search_searxng_url: str | None

    # Effective values (after applying overrides to defaults)
    effective_homebox_url: str
    effective_image_quality: str

    # Available options for dropdowns
    image_quality_options: list[str] = Field(
        default=["low", "medium", "high"],
    )
    search_provider_options: list[str] = Field(
        default=["none", "tavily", "google_cse", "searxng"],
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/settings/app-preferences", response_model=AppPreferencesResponse)
async def get_app_preferences() -> AppPreferencesResponse:
    """Get current app preferences with effective values."""
    prefs = load_app_preferences()

    return AppPreferencesResponse(
        homebox_url_override=prefs.homebox_url_override,
        image_quality_override=prefs.image_quality_override,
        duplicate_detection_enabled=prefs.duplicate_detection_enabled,
        enrichment_enabled=prefs.enrichment_enabled,
        enrichment_auto_enrich=prefs.enrichment_auto_enrich,
        enrichment_cache_ttl_hours=prefs.enrichment_cache_ttl_hours,
        search_provider=prefs.search_provider,
        search_tavily_api_key=prefs.search_tavily_api_key,
        search_google_api_key=prefs.search_google_api_key,
        search_google_engine_id=prefs.search_google_engine_id,
        search_searxng_url=prefs.search_searxng_url,
        effective_homebox_url=get_effective_homebox_url(prefs),
        effective_image_quality=get_effective_image_quality(prefs),
    )


@router.put("/settings/app-preferences", response_model=AppPreferencesResponse)
async def update_app_preferences(
    input_prefs: AppPreferencesInput,
) -> AppPreferencesResponse:
    """Update app preferences."""
    # Clean up empty strings to None
    homebox_url = input_prefs.homebox_url_override
    if homebox_url is not None:
        homebox_url = homebox_url.strip() or None

    image_quality = input_prefs.image_quality_override
    if image_quality is not None:
        image_quality = image_quality.strip() or None

    # Clean up search provider settings
    tavily_key = input_prefs.search_tavily_api_key
    if tavily_key is not None:
        tavily_key = tavily_key.strip() or None

    google_key = input_prefs.search_google_api_key
    if google_key is not None:
        google_key = google_key.strip() or None

    google_engine_id = input_prefs.search_google_engine_id
    if google_engine_id is not None:
        google_engine_id = google_engine_id.strip() or None

    searxng_url = input_prefs.search_searxng_url
    if searxng_url is not None:
        searxng_url = searxng_url.strip() or None

    prefs = AppPreferences(
        homebox_url_override=homebox_url,
        image_quality_override=image_quality,
        duplicate_detection_enabled=input_prefs.duplicate_detection_enabled,
        enrichment_enabled=input_prefs.enrichment_enabled,
        enrichment_auto_enrich=input_prefs.enrichment_auto_enrich,
        enrichment_cache_ttl_hours=input_prefs.enrichment_cache_ttl_hours,
        search_provider=input_prefs.search_provider,
        search_tavily_api_key=tavily_key,
        search_google_api_key=google_key,
        search_google_engine_id=google_engine_id,
        search_searxng_url=searxng_url,
    )

    save_app_preferences(prefs)

    return AppPreferencesResponse(
        homebox_url_override=prefs.homebox_url_override,
        image_quality_override=prefs.image_quality_override,
        duplicate_detection_enabled=prefs.duplicate_detection_enabled,
        enrichment_enabled=prefs.enrichment_enabled,
        enrichment_auto_enrich=prefs.enrichment_auto_enrich,
        enrichment_cache_ttl_hours=prefs.enrichment_cache_ttl_hours,
        search_provider=prefs.search_provider,
        search_tavily_api_key=prefs.search_tavily_api_key,
        search_google_api_key=prefs.search_google_api_key,
        search_google_engine_id=prefs.search_google_engine_id,
        search_searxng_url=prefs.search_searxng_url,
        effective_homebox_url=get_effective_homebox_url(prefs),
        effective_image_quality=get_effective_image_quality(prefs),
    )
