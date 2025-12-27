"""Pydantic request/response schemas for the API."""

from .auth import LoginRequest, LoginResponse
from .items import BatchCreateRequest, ItemInput
from .locations import LocationCreate, LocationUpdate
from .vision import (
    AdvancedItemDetails,
    CorrectedItemResponse,
    CorrectionResponse,
    DetectedItemResponse,
    DetectionResponse,
    ItemBaseMixin,
    ItemExtendedFieldsMixin,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    # Items
    "ItemInput",
    "BatchCreateRequest",
    # Locations
    "LocationCreate",
    "LocationUpdate",
    # Vision - Base mixins
    "ItemBaseMixin",
    "ItemExtendedFieldsMixin",
    # Vision - Detection
    "DetectedItemResponse",
    "DetectionResponse",
    "AdvancedItemDetails",
    # Vision - Correction
    "CorrectedItemResponse",
    "CorrectionResponse",
]

