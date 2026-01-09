"""Data models for vision-based item detection.

Pydantic models for representing items detected by AI vision.
LiteLLM supports Pydantic models for structured output, so we define
DetectedItem as a Pydantic BaseModel for automatic validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from ...ai.llm import TokenUsage


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

    # Grouping field (used only in grouped/batch detection)
    image_indices: list[int] | None = None

    def to_create_payload(self) -> dict[str, str | int | list[str]]:
        """Convert to payload for Homebox item creation API.

        The API accepts names up to 255 characters and descriptions up to 1000
        characters. Values are clamped to stay within those limits.

        Note: This returns only the fields accepted during item creation.
        Use `get_extended_fields_payload()` for fields that require an update.

        Returns:
            A dictionary suitable for POSTing to the Homebox items endpoint.
        """
        name = (self.name or "Untitled item").strip()[:255]
        description = (self.description or "Created via Homebox Companion.").strip()[:1000]

        payload: dict[str, str | int | list[str]] = {
            "name": name,
            "description": description,
            "quantity": max(int(self.quantity or 1), 1),
        }

        if self.location_id:
            payload["locationId"] = self.location_id
        if self.label_ids:
            payload["labelIds"] = self.label_ids
        return payload

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

    @staticmethod
    def from_raw_items(raw_items: Iterable[dict]) -> list[DetectedItem]:
        """Create DetectedItem instances from LLM output dictionaries.

        Args:
            raw_items: Iterable of dictionaries from the LLM response.

        Returns:
            List of validated DetectedItem instances.
        """
        detected: list[DetectedItem] = []
        for item in raw_items:
            name = str(item.get("name", "")).strip()
            if not name:
                continue

            quantity_raw = item.get("quantity", 1)
            try:
                quantity = int(quantity_raw)
            except (TypeError, ValueError):
                quantity = 1

            raw_label_ids = item.get("labelIds") or item.get("label_ids")
            label_ids: list[str] | None = None
            if isinstance(raw_label_ids, Iterable) and not isinstance(raw_label_ids, (str, bytes)):
                label_ids = [
                    str(label_id).strip() for label_id in raw_label_ids if str(label_id).strip()
                ]
                if not label_ids:
                    label_ids = None

            description = item.get("description")

            # Parse extended fields (may be present from enhanced detection)
            manufacturer = item.get("manufacturer")
            if manufacturer and not str(manufacturer).strip():
                manufacturer = None
            elif manufacturer:
                manufacturer = str(manufacturer).strip()

            model_number = item.get("modelNumber") or item.get("model_number")
            if model_number and not str(model_number).strip():
                model_number = None
            elif model_number:
                model_number = str(model_number).strip()

            serial_number = item.get("serialNumber") or item.get("serial_number")
            if serial_number and not str(serial_number).strip():
                serial_number = None
            elif serial_number:
                serial_number = str(serial_number).strip()

            purchase_price: float | None = None
            raw_price = item.get("purchasePrice") or item.get("purchase_price")
            if raw_price is not None:
                try:
                    purchase_price = float(raw_price)
                    if purchase_price <= 0:
                        purchase_price = None
                except (TypeError, ValueError):
                    purchase_price = None

            purchase_from = item.get("purchaseFrom") or item.get("purchase_from")
            if purchase_from and not str(purchase_from).strip():
                purchase_from = None
            elif purchase_from:
                purchase_from = str(purchase_from).strip()

            notes = item.get("notes")
            if notes and not str(notes).strip():
                notes = None
            elif notes:
                notes = str(notes).strip()

            # Parse image_indices for grouped detection
            raw_indices = item.get("imageIndices") or item.get("image_indices")
            image_indices: list[int] | None = None
            if isinstance(raw_indices, Iterable) and not isinstance(raw_indices, (str, bytes)):
                try:
                    image_indices = [int(idx) for idx in raw_indices]
                except (TypeError, ValueError):
                    image_indices = None

            detected.append(
                DetectedItem(
                    name=name,
                    quantity=max(quantity, 1),
                    description=description,
                    label_ids=label_ids,
                    manufacturer=manufacturer,
                    model_number=model_number,
                    serial_number=serial_number,
                    purchase_price=purchase_price,
                    purchase_from=purchase_from,
                    notes=notes,
                    image_indices=image_indices,
                )
            )
        return detected


@dataclass
class DetectionResult:
    """Result from item detection including both items and token usage.

    Attributes:
        items: List of detected items from the image(s).
        usage: Token usage statistics from the LLM call(s).
    """

    items: list[DetectedItem] = field(default_factory=list)
    usage: TokenUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "items": [item.model_dump() for item in self.items],
            "usage": self.usage.to_dict() if self.usage else None,
        }
