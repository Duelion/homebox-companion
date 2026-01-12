"""Data models for vision-based item detection.

Pydantic models for representing items detected by AI vision.
LiteLLM supports Pydantic models for structured output, so we define
DetectedItem as a Pydantic BaseModel for automatic validation.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class DetectedItem(BaseModel):
    """Structured representation for objects detected in an image.

    This class represents an item that has been identified by the AI vision
    model and can be created in Homebox. LiteLLM will validate the LLM output
    against this schema automatically.

    Extended fields (manufacturer, model_number, etc.) require an update
    after item creation since Homebox API doesn't accept them during POST.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str, Field(min_length=1, max_length=255)]
    quantity: int = Field(default=1, ge=1)
    description: Annotated[str, Field(max_length=1000)] | None = None
    location_id: str | None = Field(default=None, alias="locationId")
    label_ids: list[str] | None = Field(default=None, alias="labelIds")

    # Extended fields (can only be set via update, not create)
    manufacturer: Annotated[str, Field(max_length=255)] | None = None
    model_number: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="modelNumber")
    serial_number: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="serialNumber")
    purchase_price: float | None = Field(default=None, gt=0, alias="purchasePrice")
    purchase_from: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="purchaseFrom")
    notes: Annotated[str, Field(max_length=1000)] | None = None

    def get_extended_fields_payload(self) -> dict[str, str | float] | None:
        """Get extended fields that require an update after item creation.

        These fields (manufacturer, modelNumber, serialNumber, purchasePrice,
        purchaseFrom, notes) cannot be set during item creation and must be
        added via a subsequent PUT request.

        Returns:
            A dictionary with extended fields if any are present, or None.
        """
        payload = self.model_dump(
            by_alias=True,
            exclude_unset=True,
            exclude_none=True,
            include={"manufacturer", "model_number", "serial_number", "purchase_price", "purchase_from", "notes"},
        )
        return payload if payload else None

    def has_extended_fields(self) -> bool:
        """Check if this item has any extended fields that need updating."""
        from ...homebox.models import has_extended_fields

        return has_extended_fields(
            self.manufacturer,
            self.model_number,
            self.serial_number,
            self.purchase_price,
            self.purchase_from,
            self.notes,
        )
