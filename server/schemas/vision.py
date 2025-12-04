"""Vision tool request/response schemas."""

from pydantic import BaseModel


class DetectedItemResponse(BaseModel):
    """Detected item from image analysis."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None
    # Extended fields (extracted when visible in image)
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None


class DetectionResponse(BaseModel):
    """Response from image detection."""

    items: list[DetectedItemResponse]
    message: str = "Detection complete"


class AdvancedItemDetails(BaseModel):
    """Detailed item information from AI analysis."""

    name: str | None = None
    description: str | None = None
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = None
    notes: str | None = None
    label_ids: list[str] | None = None


class MergeItemsRequest(BaseModel):
    """Request to merge multiple items into one."""

    items: list[dict]


class MergedItemResponse(BaseModel):
    """Response with merged item data."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None


class CorrectedItemResponse(BaseModel):
    """A corrected item from AI analysis."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None
    # Extended fields
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None


class CorrectionResponse(BaseModel):
    """Response with corrected item(s)."""

    items: list[CorrectedItemResponse]
    message: str = "Correction complete"


class BatchImageConfig(BaseModel):
    """Configuration for a single image in batch detection."""

    single_item: bool = False
    extra_instructions: str | None = None


class BatchDetectionResult(BaseModel):
    """Detection result for a single image in batch."""

    image_index: int
    success: bool
    items: list[DetectedItemResponse] = []
    error: str | None = None


class BatchDetectionResponse(BaseModel):
    """Response from batch image detection."""

    results: list[BatchDetectionResult]
    total_items: int
    successful_images: int
    failed_images: int
    message: str = "Batch detection complete"

