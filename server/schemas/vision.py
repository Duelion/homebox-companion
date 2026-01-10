"""Vision tool request/response schemas."""

from pydantic import BaseModel, Field


class TokenUsageResponse(BaseModel):
    """Token usage statistics from LLM call."""

    prompt_tokens: int = Field(default=0, description="Number of tokens in the prompt")
    completion_tokens: int = Field(default=0, description="Number of tokens in the completion")
    total_tokens: int = Field(default=0, description="Total tokens used")
    provider: str = Field(default="unknown", description="LLM provider name")


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

    # Grouping field - only populated when using grouped/auto-group detection
    image_indices: list[int] | None = Field(
        default=None,
        description="Indices of images showing this item (0-based). Only set in grouped detection mode.",
    )


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
    usage: TokenUsageResponse | None = Field(
        default=None, description="Token usage statistics (if enabled)"
    )


class AdvancedItemDetails(ItemExtendedFieldsMixin):
    """Detailed item information from AI analysis.

    All fields are optional since they may not be extractable from images.
    """

    name: str | None = None
    description: str | None = None
    label_ids: list[str] | None = None


class CorrectedItemResponse(ItemBaseMixin, ItemExtendedFieldsMixin):
    """A corrected item from AI analysis."""

    # Grouping field - for consistency with DetectedItemResponse
    image_indices: list[int] | None = Field(
        default=None,
        description="Indices of images showing this item (0-based).",
    )


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
    usage: TokenUsageResponse | None = Field(
        default=None, description="Token usage statistics for this image"
    )


class BatchDetectionResponse(BaseModel):
    """Response from batch image detection."""

    results: list[BatchDetectionResult]
    total_items: int
    successful_images: int
    failed_images: int
    message: str = "Batch detection complete"
    total_usage: TokenUsageResponse | None = Field(
        default=None, description="Aggregated token usage across all images"
    )


class GroupedDetectionResponse(BaseModel):
    """Response from grouped/auto-group batch detection.

    In grouped mode, all images are analyzed together to identify
    unique items. Each item includes image_indices showing which
    images contain that item.
    """

    items: list[DetectedItemResponse] = Field(
        description="Unique items detected across all images, with image_indices"
    )
    total_images: int = Field(description="Total number of images analyzed")
    message: str = "Grouped detection complete"
    usage: TokenUsageResponse | None = Field(
        default=None, description="Token usage statistics (if enabled)"
    )
