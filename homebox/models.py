"""Shared data models used across the Homebox client and helpers."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class DetectedItem:
    """Structured representation for objects found in an image."""

    name: str
    quantity: int
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None

    def as_item_payload(self) -> dict[str, str | int | list[str]]:
        """Convert the detected item into the payload expected by the API.

        The API accepts names up to 255 characters and descriptions up to 1000
        characters. Values are clamped to stay within those limits.
        """

        name = (self.name or "Untitled item").strip()
        name = name[:255] if len(name) > 255 else name

        description = (self.description or "Created via OpenAI vision analysis.").strip()
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
        """Create ``DetectedItem`` instances from LLM output dictionaries."""

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

            description = item.get("description")
            detected.append(
                DetectedItem(
                    name=name,
                    quantity=quantity,
                    description=description,
                )
            )
        return detected
