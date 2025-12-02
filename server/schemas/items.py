"""Item-related request/response schemas."""

from pydantic import BaseModel


class ItemInput(BaseModel):
    """Item data for creation with all Homebox fields."""

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None
    # Advanced fields
    serial_number: str | None = None
    model_number: str | None = None
    manufacturer: str | None = None
    purchase_price: float | None = None
    purchase_from: str | None = None
    notes: str | None = None
    insured: bool = False


class BatchCreateRequest(BaseModel):
    """Batch item creation request."""

    items: list[ItemInput]
    location_id: str | None = None
