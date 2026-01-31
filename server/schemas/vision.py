"""Vision tool request/response schemas."""

from pydantic import BaseModel, Field


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
    tag_ids: list[str] | None = None


class DuplicateMatchResponse(BaseModel):
    """Details of an existing item that matches a detected item's serial number."""

    item_id: str
    item_name: str
    serial_number: str
    location_name: str | None = None


class DetectedItemResponse(ItemBaseMixin, ItemExtendedFieldsMixin):
    """Detected item from image analysis."""

    # Duplicate detection - populated if serial number matches an existing item
    duplicate_match: DuplicateMatchResponse | None = None


class CompressedImage(BaseModel):
    """Compressed image data for Homebox upload."""

    data: str = Field(description="Base64-encoded compressed image")
    mime_type: str = Field(description="MIME type (typically 'image/jpeg')")


class DetectionResponse(BaseModel):
    """Response from image detection."""

    items: list[DetectedItemResponse]
    message: str = "Detection complete"
    compressed_images: list[CompressedImage] = Field(
        default_factory=list, description="Compressed versions of images for Homebox upload"
    )


class AdvancedItemDetails(ItemExtendedFieldsMixin):
    """Detailed item information from AI analysis.

    All fields are optional since they may not be extractable from images.
    """

    name: str | None = None
    description: str | None = None
    tag_ids: list[str] | None = None


class CorrectedItemResponse(ItemBaseMixin, ItemExtendedFieldsMixin):
    """A corrected item from AI analysis."""

    pass


class CorrectionResponse(BaseModel):
    """Response with corrected item(s)."""

    items: list[CorrectedItemResponse]
    message: str = "Correction complete"


class BatchDetectionResult(BaseModel):
    """Detection result for a single image in batch."""

    image_index: int
    success: bool
    items: list[DetectedItemResponse] = Field(default_factory=list)
    error: str | None = None


class BatchDetectionResponse(BaseModel):
    """Response from batch image detection."""

    results: list[BatchDetectionResult]
    total_items: int
    successful_images: int
    failed_images: int
    message: str = "Batch detection complete"
