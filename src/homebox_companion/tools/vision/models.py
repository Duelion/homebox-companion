"""Data models for vision-based item detection."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class DetectedItem:
    """Structured representation for objects detected in an image.

    This class represents an item that has been identified by the AI vision
    model and can be created in Homebox.

    Attributes:
        name: The item name (max 255 characters).
        quantity: Number of this item detected (default: 1).
        description: Optional description of the item (max 1000 characters).
        location_id: Optional Homebox location ID where the item should be stored.
        label_ids: Optional list of Homebox label IDs to attach to the item.

    Extended fields (require update after creation):
        manufacturer: Brand/manufacturer name when visible on the item.
        model_number: Model or part number when visible on labels/packaging.
        serial_number: Serial number when visible on stickers/engravings.
        purchase_price: Price when visible on tags/receipts.
        purchase_from: Retailer name when visible on packaging/receipts.
        notes: Notable observations about condition, wear, or special features.
    """

    name: str
    quantity: int
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None
    # Extended fields (can only be set via update, not create)
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None

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
            Empty strings after stripping whitespace are excluded.
        """
        payload: dict[str, str | float] = {}

        if self.manufacturer:
            value = str(self.manufacturer).strip()[:255]
            if value:  # Exclude empty strings after strip
                payload["manufacturer"] = value
        if self.model_number:
            value = str(self.model_number).strip()[:255]
            if value:
                payload["modelNumber"] = value
        if self.serial_number:
            value = str(self.serial_number).strip()[:255]
            if value:
                payload["serialNumber"] = value
        if self.purchase_price is not None and self.purchase_price > 0:
            payload["purchasePrice"] = self.purchase_price
        if self.purchase_from:
            value = str(self.purchase_from).strip()[:255]
            if value:
                payload["purchaseFrom"] = value
        if self.notes:
            value = str(self.notes).strip()[:1000]
            if value:
                payload["notes"] = value

        return payload if payload else None

    def has_extended_fields(self) -> bool:
        """Check if this item has any extended fields that need updating."""
        return bool(
            self.manufacturer
            or self.model_number
            or self.serial_number
            or (self.purchase_price is not None and self.purchase_price > 0)
            or self.purchase_from
            or self.notes
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
                    str(label_id).strip()
                    for label_id in raw_label_ids
                    if str(label_id).strip()
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
                )
            )
        return detected









