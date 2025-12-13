"""Data models for Homebox API entities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Location:
    """A location in the Homebox inventory system."""

    id: str
    name: str
    description: str = ""
    item_count: int = 0
    children: list[Location] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> Location:
        """Create a Location from API response data."""
        children = [cls.from_api(c) for c in data.get("children", [])]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            item_count=data.get("itemCount", 0),
            children=children,
        )


@dataclass
class Label:
    """A label in the Homebox inventory system."""

    id: str
    name: str
    description: str = ""
    color: str = ""

    @classmethod
    def from_api(cls, data: dict) -> Label:
        """Create a Label from API response data."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            color=data.get("color", ""),
        )


@dataclass
class Item:
    """An item in the Homebox inventory system."""

    id: str
    name: str
    quantity: int = 1
    description: str = ""
    location_id: str | None = None
    label_ids: list[str] = field(default_factory=list)
    # Extended fields
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None
    insured: bool = False

    @classmethod
    def from_api(cls, data: dict) -> Item:
        """Create an Item from API response data."""
        location = data.get("location", {})
        labels = data.get("labels", [])
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            quantity=data.get("quantity", 1),
            description=data.get("description", ""),
            location_id=location.get("id") if location else None,
            label_ids=[lbl.get("id") for lbl in labels if lbl.get("id")],
            manufacturer=data.get("manufacturer"),
            model_number=data.get("modelNumber"),
            serial_number=data.get("serialNumber"),
            purchase_price=data.get("purchasePrice"),
            purchase_from=data.get("purchaseFrom"),
            notes=data.get("notes"),
            insured=data.get("insured", False),
        )


@dataclass
class ItemCreate:
    """Data for creating a new item in Homebox."""

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None
    parent_id: str | None = None  # For sub-item relationships

    def to_payload(self) -> dict:
        """Convert to API payload for item creation."""
        name = (self.name or "Untitled item").strip()[:255]
        description = (self.description or "Created via Homebox Companion.").strip()[:1000]

        payload: dict = {
            "name": name,
            "description": description,
            "quantity": max(int(self.quantity or 1), 1),
        }

        if self.location_id:
            payload["locationId"] = self.location_id
        if self.label_ids:
            payload["labelIds"] = self.label_ids
        if self.parent_id:
            payload["parentId"] = self.parent_id

        return payload


@dataclass
class ItemUpdate:
    """Data for updating an existing item in Homebox."""

    name: str | None = None
    quantity: int | None = None
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None
    insured: bool | None = None

    def to_payload(self) -> dict:
        """Convert to API payload for item update."""
        payload: dict = {}

        if self.name is not None:
            payload["name"] = str(self.name).strip()[:255]
        if self.quantity is not None:
            payload["quantity"] = max(int(self.quantity), 1)
        if self.description is not None:
            payload["description"] = str(self.description).strip()[:1000]
        if self.location_id is not None:
            payload["locationId"] = self.location_id
        if self.label_ids is not None:
            payload["labelIds"] = self.label_ids
        if self.manufacturer is not None:
            payload["manufacturer"] = str(self.manufacturer).strip()[:255]
        if self.model_number is not None:
            payload["modelNumber"] = str(self.model_number).strip()[:255]
        if self.serial_number is not None:
            payload["serialNumber"] = str(self.serial_number).strip()[:255]
        if self.purchase_price is not None:
            payload["purchasePrice"] = self.purchase_price
        if self.purchase_from is not None:
            payload["purchaseFrom"] = str(self.purchase_from).strip()[:255]
        if self.notes is not None:
            payload["notes"] = str(self.notes).strip()[:1000]
        if self.insured is not None:
            payload["insured"] = self.insured

        return payload

    def has_extended_fields(self) -> bool:
        """Check if any extended fields are set."""
        return any([
            self.manufacturer,
            self.model_number,
            self.serial_number,
            self.purchase_price is not None and self.purchase_price > 0,
            self.purchase_from,
            self.notes,
        ])


@dataclass
class Attachment:
    """An attachment (image) for an item in Homebox."""

    id: str
    type: str
    document_id: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> Attachment:
        """Create an Attachment from API response data."""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            document_id=data.get("document", {}).get("id") if data.get("document") else None,
        )
