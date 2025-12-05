"""Location request/response schemas."""

from pydantic import BaseModel


class LocationCreate(BaseModel):
    """Request body for creating a location."""

    name: str
    description: str = ""
    parent_id: str | None = None


class LocationUpdate(BaseModel):
    """Request body for updating a location."""

    name: str
    description: str = ""
    parent_id: str | None = None

