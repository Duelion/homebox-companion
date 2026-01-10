"""Session and state models for crash-proof capture sessions.

These models define the data structures used by StateManager for
tracking image processing state and session metadata.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ImageStatus(str, Enum):
    """Status of an image in the processing pipeline."""

    PENDING = "pending"  # Waiting to be processed
    PROCESSING = "processing"  # Currently being analyzed by AI
    COMPLETED = "completed"  # Successfully processed, ready for review
    FAILED = "failed"  # Failed after max retries
    PUSHED = "pushed"  # Successfully pushed to Homebox


class SessionStatus(str, Enum):
    """Status of a capture session."""

    CREATED = "created"  # Session initialized, no images yet
    PROCESSING = "processing"  # At least one image being processed
    READY = "ready"  # All images processed successfully
    MIXED = "mixed"  # Some completed, some failed
    PUSHING = "pushing"  # Currently pushing to Homebox
    PUSHED = "pushed"  # All items pushed to Homebox
    PARTIAL = "partial"  # Some items pushed, some failed
    ABANDONED = "abandoned"  # User abandoned the session


class SessionStats(BaseModel):
    """Statistics for a capture session."""

    total: int = 0
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    pushed: int = 0


class HomeboxConfig(BaseModel):
    """Homebox connection settings for a session."""

    url: str
    location_id: str | None = None
    location_name: str | None = None


class SessionSettings(BaseModel):
    """Processing settings captured at session creation."""

    ai_provider: str = "litellm"
    ai_model: str = ""
    enrichment_enabled: bool = False
    attach_photos: bool = True


class SessionMeta(BaseModel):
    """Session metadata stored in session_meta.json."""

    session_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: SessionStatus = SessionStatus.CREATED
    homebox: HomeboxConfig
    settings: SessionSettings = Field(default_factory=SessionSettings)
    stats: SessionStats = Field(default_factory=SessionStats)


class ConfidenceScores(BaseModel):
    """Confidence scores for extracted fields."""

    overall: float = 0.0
    serial_number: float | None = None
    model_number: float | None = None
    manufacturer: float | None = None
    name: float | None = None


class ExtractedFields(BaseModel):
    """Fields extracted from an image by AI."""

    name: str = ""
    manufacturer: str = ""
    model_number: str = ""
    serial_number: str = ""
    quantity: int = 1
    mac_address: str | None = None
    fcc_id: str | None = None
    notes: str | None = None


class EnrichmentData(BaseModel):
    """Data from web enrichment lookup."""

    enriched: bool = False
    enriched_at: datetime | None = None
    source: str | None = None
    description: str | None = None
    features: list[str] = Field(default_factory=list)
    msrp: float | None = None
    release_year: int | None = None
    category: str | None = None


class UserEdits(BaseModel):
    """Tracking for user edits to extracted data."""

    edited: bool = False
    edited_at: datetime | None = None
    changes: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Full extraction result for an image, stored as JSON."""

    image_id: str
    extracted_at: datetime = Field(default_factory=datetime.now)
    ai_provider: str = ""
    ai_model: str = ""

    fields: ExtractedFields = Field(default_factory=ExtractedFields)
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)
    enrichment: EnrichmentData = Field(default_factory=EnrichmentData)
    user_edits: UserEdits = Field(default_factory=UserEdits)

    raw_ai_response: str | None = None
