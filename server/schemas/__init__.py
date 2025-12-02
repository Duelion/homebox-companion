"""Pydantic request/response schemas for the API."""

from .auth import LoginRequest, LoginResponse
from .items import BatchCreateRequest, ItemInput
from .vision import (
    AdvancedItemDetails,
    CorrectedItemResponse,
    CorrectionResponse,
    DetectedItemResponse,
    DetectionResponse,
    MergedItemResponse,
    MergeItemsRequest,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    # Items
    "ItemInput",
    "BatchCreateRequest",
    # Vision
    "DetectedItemResponse",
    "DetectionResponse",
    "AdvancedItemDetails",
    "MergeItemsRequest",
    "MergedItemResponse",
    "CorrectedItemResponse",
    "CorrectionResponse",
]
