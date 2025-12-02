"""Item-related schemas for the Homebox Vision API."""

from pydantic import BaseModel


class ItemInput(BaseModel):
    """Item data for creation with all Homebox fields.

    This schema represents the data needed to create an item in Homebox,
    including both basic fields (supported during creation) and extended
    fields (which require a follow-up update).
    """

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None

    # Extended fields (applied via update after creation)
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None
    insured: bool = False


class BatchCreateRequest(BaseModel):
    """Request to create multiple items at once.

    Items can specify their own location_id, or fall back to the
    request-level location_id.
    """

    items: list[ItemInput]
    location_id: str | None = None
