"""Item-related request/response schemas."""

from pydantic import BaseModel, Field


class ItemInput(BaseModel):
    """Item data for creation with all Homebox fields.

    Note: In Homebox 0.26+, both ``location_id`` and ``parent_id`` map to the
    API's ``parentId`` field. ``parent_id`` (a parent item picked in the UI)
    takes precedence over ``location_id``. The new item inherits its location
    from that parent, except on Homebox 0.27 when the parent has its own
    location override: Homebox does not pass that on, so the selected location
    is sent as the new item's ``locationId``.
    """

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None  # Location to place the item in
    tag_ids: list[str] | None = None
    parent_id: str | None = None  # Parent item to nest under; takes precedence (both map to parentId)
    # Advanced fields
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    purchase_from: str | None = None
    notes: str | None = None
    insured: bool = False
    # Custom fields: map of display name → text value
    custom_fields: dict[str, str] | None = None


class BatchCreateRequest(BaseModel):
    """Batch item creation request."""

    items: list[ItemInput]
    location_id: str | None = None
