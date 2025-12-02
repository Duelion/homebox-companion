"""Detection and AI analysis schemas for the Homebox Vision API."""

from pydantic import BaseModel


class DetectedItemResponse(BaseModel):
    """A single item detected from image analysis.

    Contains both basic fields and extended fields that may have been
    extracted when visible in the image.
    """

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
    """Response from image detection endpoint."""

    items: list[DetectedItemResponse]
    message: str = "Detection complete"


class AdvancedItemDetails(BaseModel):
    """Detailed item information from multi-image AI analysis.

    This schema represents the detailed fields that can be extracted
    when analyzing multiple images of a single item.
    """

    name: str | None = None
    description: str | None = None
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = None
    notes: str | None = None
    label_ids: list[str] | None = None


class MergeItemsRequest(BaseModel):
    """Request to merge multiple similar items into one."""

    items: list[dict]


class MergedItemResponse(BaseModel):
    """Response with the merged item data."""

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None


class CorrectedItemResponse(BaseModel):
    """A single corrected item from AI analysis.

    Used when the user provides feedback to correct or split
    a previously detected item.
    """

    name: str
    quantity: int
    description: str | None = None
    label_ids: list[str] | None = None


class CorrectionResponse(BaseModel):
    """Response with corrected item(s).

    May contain multiple items if the user indicated the original
    detection should be split into separate items.
    """

    items: list[CorrectedItemResponse]
    message: str = "Correction complete"
