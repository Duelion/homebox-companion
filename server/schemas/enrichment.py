"""Pydantic schemas for enrichment API endpoints."""

from pydantic import BaseModel, Field


class EnrichmentRequest(BaseModel):
    """Request to enrich a product with specifications."""

    manufacturer: str = Field(default="", description="Product manufacturer")
    model_number: str = Field(..., description="Product model/part number")
    product_name: str = Field(default="", description="Optional product name hint")


class EnrichmentResponse(BaseModel):
    """Response with enriched product data."""

    enriched: bool = Field(description="Whether enrichment was successful")
    source: str = Field(description="Source of enrichment data (ai_knowledge, cache, none)")
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


class EnrichmentSettingsRequest(BaseModel):
    """Request to update enrichment settings."""

    enabled: bool = Field(description="Whether enrichment is enabled")
    auto_enrich: bool = Field(
        default=False, description="Automatically enrich items after detection"
    )
    cache_ttl_hours: int = Field(
        default=24, ge=1, le=168, description="Cache time-to-live in hours (1-168)"
    )


class EnrichmentSettingsResponse(BaseModel):
    """Response with current enrichment settings."""

    enabled: bool = Field(description="Whether enrichment is enabled")
    auto_enrich: bool = Field(description="Automatically enrich items after detection")
    cache_ttl_hours: int = Field(description="Cache time-to-live in hours")
    cache_entries: int = Field(description="Number of cached enrichment results")


class ClearCacheResponse(BaseModel):
    """Response from clearing the enrichment cache."""

    cleared_count: int = Field(description="Number of cache entries cleared")
    message: str = Field(description="Status message")
