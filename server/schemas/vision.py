"""Vision tool request/response schemas."""

from pydantic import BaseModel


# Base mixin for item extended fields to reduce duplication
class ItemExtendedFieldsMixin(BaseModel):
    """Mixin containing extended fields shared across item schemas."""

    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None


class ItemBaseMixin(BaseModel):
    """Mixin containing core fields shared across item schemas."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None


class DetectedItemResponse(ItemBaseMixin, ItemExtendedFieldsMixin):
    """Detected item from image analysis."""

    pass


class DetectionResponse(BaseModel):
    """Response from image detection."""

    items: list[DetectedItemResponse]
    message: str = "Detection complete"


class AdvancedItemDetails(ItemExtendedFieldsMixin):
    """Detailed item information from AI analysis.

    All fields are optional since they may not be extractable from images.
    """

    name: str | None = None
    description: str | None = None
    label_ids: list[str] | None = None


class MergeItemInput(BaseModel):
    """Input item for merge request with typed fields."""

    name: str
    quantity: int = 1
    description: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None


class MergeItemsRequest(BaseModel):
    """Request to merge multiple items into one."""

    items: list[MergeItemInput]


class MergedItemResponse(ItemBaseMixin):
    """Response with merged item data."""

    pass


class CorrectedItemResponse(ItemBaseMixin, ItemExtendedFieldsMixin):
    """A corrected item from AI analysis."""

    pass


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

