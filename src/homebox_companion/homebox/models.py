"""Data models for Homebox API entities.

Pydantic-first architecture: These models handle parsing, validation, and
serialization automatically. Use `model_validate()` to parse API responses
and `model_dump(by_alias=True)` to generate API payloads.

Field aliases map Python snake_case to API camelCase automatically via
alias_generator, with explicit overrides where needed.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Location",
    "Tag",
    "Item",
    "ItemCreate",
    "ItemUpdate",
    "Attachment",
    "has_extended_fields",
]


def has_extended_fields(
    manufacturer: str | None,
    model_number: str | None,
    serial_number: str | None,
    purchase_price: float | None,
    purchase_from: str | None,
    notes: str | None,
) -> bool:
    """Check if any extended item fields are set.

    Extended fields are those that cannot be set during item creation
    and require a subsequent update API call.

    This is a shared utility used by ItemUpdate and DetectedItem.
    """
    return any(
        [
            manufacturer,
            model_number,
            serial_number,
            purchase_price is not None and purchase_price > 0,
            purchase_from,
            notes,
        ]
    )


# =============================================================================
# Core Domain Models (API Contract - Strict)
# =============================================================================


class Location(BaseModel):
    """A location in the Homebox inventory system."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    name: str = ""
    description: str = ""
    item_count: int = Field(default=0, alias="itemCount")
    children: list[Location] = Field(default_factory=list)


class Tag(BaseModel):
    """A tag in the Homebox inventory system."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str = ""
    color: str = ""


class Item(BaseModel):
    """An item in the Homebox inventory system."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: Annotated[str, Field(min_length=1, max_length=255)]
    quantity: int = Field(default=1, ge=0)
    description: Annotated[str, Field(max_length=1000)] = ""
    location_id: str | None = Field(default=None, alias="locationId")
    tag_ids: list[str] = Field(default_factory=list, alias="tagIds")
    # Extended fields
    manufacturer: str | None = None
    model_number: str | None = Field(default=None, alias="modelNumber")
    serial_number: str | None = Field(default=None, alias="serialNumber")
    purchase_price: float | None = Field(default=None, alias="purchasePrice")
    purchase_from: str | None = Field(default=None, alias="purchaseFrom")
    notes: str | None = Field(default=None)
    insured: bool = False


# =============================================================================
# Input Models (For Create/Update Operations)
# =============================================================================


class ItemCreate(BaseModel):
    """Data for creating a new item in Homebox.

    Use `model_dump(by_alias=True, exclude_unset=True)` to generate the API payload.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str, Field(min_length=1, max_length=255)]
    quantity: int = Field(default=1, ge=1)
    description: Annotated[str, Field(max_length=1000)] = ""
    location_id: str | None = Field(default=None, alias="locationId")
    tag_ids: list[str] | None = Field(default=None, alias="tagIds")
    parent_id: str | None = Field(default=None, alias="parentId")


class ItemUpdate(BaseModel):
    """Data for updating an existing item in Homebox.

    Only set fields that should be updated. Use `model_dump(by_alias=True, exclude_unset=True)`
    to generate a partial update payload.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str, Field(max_length=255)] | None = None
    quantity: int | None = Field(default=None, ge=1)
    description: Annotated[str, Field(max_length=1000)] | None = None
    location_id: str | None = Field(default=None, alias="locationId")
    tag_ids: list[str] | None = Field(default=None, alias="tagIds")
    manufacturer: Annotated[str, Field(max_length=255)] | None = None
    model_number: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="modelNumber")
    serial_number: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="serialNumber")
    purchase_price: float | None = Field(default=None, alias="purchasePrice")
    purchase_from: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="purchaseFrom")
    notes: Annotated[str, Field(max_length=1000)] | None = Field(default=None)
    insured: bool | None = Field(default=None)

    def has_extended_fields(self) -> bool:
        """Check if any extended fields are set."""
        return has_extended_fields(
            self.manufacturer,
            self.model_number,
            self.serial_number,
            self.purchase_price,
            self.purchase_from,
            self.notes,
        )


class Attachment(BaseModel):
    """An attachment (image) for an item in Homebox."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    document_id: str | None = Field(default=None, alias="documentId")
