"""Item-related request/response schemas."""

from pydantic import BaseModel


class ItemInput(BaseModel):
    """Item data for creation with all Homebox fields.

    Note: In Homebox 0.26+, both ``location_id`` and ``parent_id`` map to the
    API's ``parentId`` field. ``location_id`` is the primary field (container
    selection from the UI), while ``parent_id`` is a legacy alias kept for
    backward compatibility.
    """

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None  # Container (location) to place the item in
    tag_ids: list[str] | None = None
    parent_id: str | None = None  # Legacy alias for location_id (both map to parentId)
    # Advanced fields
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None
    insured: bool = False
    # Custom fields: map of display name → text value
    custom_fields: dict[str, str] | None = None


class BatchCreateRequest(BaseModel):
    """Batch item creation request."""

    items: list[ItemInput]
    location_id: str | None = None
