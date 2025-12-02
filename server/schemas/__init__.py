"""Pydantic schemas for API request/response models.

This package contains Pydantic models organized by domain,
mirroring the router structure for consistency.
"""

from .auth import LoginRequest, LoginResponse
from .detection import (
    AdvancedItemDetails,
    CorrectedItemResponse,
    CorrectionResponse,
    DetectedItemResponse,
    DetectionResponse,
    MergedItemResponse,
    MergeItemsRequest,
)
from .items import BatchCreateRequest, ItemInput

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    # Detection
    "DetectedItemResponse",
    "DetectionResponse",
    "AdvancedItemDetails",
    "MergeItemsRequest",
    "MergedItemResponse",
    "CorrectedItemResponse",
    "CorrectionResponse",
    # Items
    "ItemInput",
    "BatchCreateRequest",
]
