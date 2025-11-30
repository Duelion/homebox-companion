"""Data types for the homebox library.

This module provides clean, Pythonic data structures for working with
Homebox inventory items.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Item:
    """An inventory item in Homebox.

    This is the primary data structure for representing items, whether
    detected from images or created manually.

    Attributes:
        name: Item name (max 255 characters).
        quantity: Number of items (default 1).
        description: Optional description (max 1000 characters).
        location_id: Optional location ID where the item is stored.
        label_ids: Optional list of label IDs to tag the item.
        id: Item ID (set by the API after creation).

    Example:
        >>> from homebox import Item
        >>> item = Item("Hammer", quantity=2, description="Steel head, wooden handle")
        >>> item.name
        'Hammer'
    """

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None
    id: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate and normalize item data."""
        self.name = (self.name or "").strip()[:255]
        self.quantity = max(int(self.quantity or 1), 1)
        if self.description:
            self.description = self.description.strip()[:1000]

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary representation.

        Returns:
            Dictionary with all non-None fields.
        """
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_api_payload(self) -> dict[str, str | int | list[str]]:
        """Convert to the payload format expected by the Homebox API.

        Returns:
            Dictionary ready to be sent to the API.
        """
        payload: dict[str, str | int | list[str]] = {
            "name": self.name or "Untitled item",
            "description": self.description or "Created via homebox-py.",
            "quantity": self.quantity,
        }
        if self.location_id:
            payload["locationId"] = self.location_id
        if self.label_ids:
            payload["labelIds"] = self.label_ids
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Item:
        """Create an Item from a dictionary (e.g., API response).

        Args:
            data: Dictionary containing item data.

        Returns:
            A new Item instance.
        """
        # Handle both camelCase (API) and snake_case (Python) keys
        label_ids = data.get("labelIds") or data.get("label_ids")
        if isinstance(label_ids, Iterable) and not isinstance(label_ids, (str, bytes)):
            label_ids = [str(lid).strip() for lid in label_ids if str(lid).strip()]
        else:
            label_ids = None

        return cls(
            name=str(data.get("name", "")).strip(),
            quantity=_parse_quantity(data.get("quantity", 1)),
            description=data.get("description"),
            location_id=data.get("locationId") or data.get("location_id"),
            label_ids=label_ids or None,
            id=data.get("id"),
        )

    @classmethod
    def from_list(cls, items: Iterable[dict[str, Any]]) -> list[Item]:
        """Create multiple Items from a list of dictionaries.

        Args:
            items: List of dictionaries containing item data.

        Returns:
            List of Item instances (empty items filtered out).
        """
        result: list[Item] = []
        for item_data in items:
            item = cls.from_dict(item_data)
            if item.name:  # Skip items with empty names
                result.append(item)
        return result


@dataclass
class Location:
    """A storage location in Homebox.

    Attributes:
        id: Location ID.
        name: Location name.
        description: Optional description.
        item_count: Number of items in this location.
    """

    id: str
    name: str
    description: str | None = None
    item_count: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Location:
        """Create a Location from a dictionary."""
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=data.get("description"),
            item_count=int(data.get("itemCount", 0)),
        )

    @classmethod
    def from_list(cls, locations: Iterable[dict[str, Any]]) -> list[Location]:
        """Create multiple Locations from a list of dictionaries."""
        return [cls.from_dict(loc) for loc in locations]


@dataclass
class Label:
    """A label/tag in Homebox.

    Attributes:
        id: Label ID.
        name: Label name.
    """

    id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Label:
        """Create a Label from a dictionary."""
        return cls(
            id=str(data.get("id", "")).strip(),
            name=str(data.get("name", "")).strip(),
        )

    @classmethod
    def from_list(cls, labels: Iterable[dict[str, Any]]) -> list[Label]:
        """Create multiple Labels from a list of dictionaries."""
        return [cls.from_dict(lbl) for lbl in labels if lbl.get("id") and lbl.get("name")]


def _parse_quantity(value: Any) -> int:
    """Safely parse a quantity value to int."""
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 1


# Backwards compatibility alias
DetectedItem = Item

__all__ = ["Item", "Location", "Label", "DetectedItem"]
