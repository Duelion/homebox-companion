"""Shared data models used across the Homebox Vision Companion."""

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
    """

    name: str
    quantity: int
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None

    def as_item_payload(self) -> dict[str, str | int | list[str]]:
        """Convert the detected item into the payload expected by the Homebox API.

        The API accepts names up to 255 characters and descriptions up to 1000
        characters. Values are clamped to stay within those limits.

        Returns:
            A dictionary suitable for POSTing to the Homebox items endpoint.
        """
        name = (self.name or "Untitled item").strip()
        name = name[:255] if len(name) > 255 else name

        description = (self.description or "Created via Homebox Vision Companion.").strip()
        if len(description) > 1000:
            description = description[:1000]

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
            detected.append(
                DetectedItem(
                    name=name,
                    quantity=max(quantity, 1),
                    description=description,
                    label_ids=label_ids,
                )
            )
        return detected

