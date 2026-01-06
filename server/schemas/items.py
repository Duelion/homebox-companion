"""Item-related request/response schemas."""

from pydantic import BaseModel


class ItemInput(BaseModel):
    """Item data for creation with all Homebox fields."""

    name: str
    quantity: int = 1
    description: str | None = None
    location_id: str | None = None
    label_ids: list[str] | None = None
    parent_id: str | None = None  # For sub-item relationships
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


# =============================================================================
# DUPLICATE CHECK SCHEMAS
# =============================================================================


class ExistingItemInfo(BaseModel):
    """Summary of an existing item in Homebox."""

    id: str
    name: str
    serial_number: str
    location_id: str | None = None
    location_name: str | None = None


class DuplicateMatch(BaseModel):
    """A match between a new item and an existing item."""

    item_index: int
    """Index of the new item in the submitted list."""

    item_name: str
    """Name of the new item."""

    serial_number: str
    """The matching serial number (normalized to uppercase)."""

    existing_item: ExistingItemInfo
    """The existing item that matches."""


class DuplicateCheckRequest(BaseModel):
    """Request to check for duplicate items by serial number."""

    items: list[ItemInput]
    """Items to check for duplicates."""


class DuplicateCheckResponse(BaseModel):
    """Response from duplicate check."""

    duplicates: list[DuplicateMatch]
    """List of items that have matching serial numbers in Homebox."""

    checked_count: int
    """Number of items that had serial numbers to check."""

    message: str
    """Summary message."""


# =============================================================================
# DUPLICATE INDEX STATUS SCHEMAS
# =============================================================================


class DuplicateIndexStatus(BaseModel):
    """Status of the duplicate detection index."""

    last_build_time: str | None
    """ISO timestamp of last full build, or null if never built."""

    last_update_time: str | None
    """ISO timestamp of last update (full or differential)."""

    total_items_indexed: int
    """Total number of items in Homebox."""

    items_with_serials: int
    """Number of items with serial numbers in the index."""

    highest_asset_id: int
    """Highest asset ID seen (used for differential updates)."""

    is_loaded: bool
    """Whether the index is currently loaded in memory."""


class DuplicateIndexRebuildResponse(BaseModel):
    """Response from index rebuild operation."""

    status: DuplicateIndexStatus
    """Updated index status after rebuild."""

    message: str
    """Summary message."""
