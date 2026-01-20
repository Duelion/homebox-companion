"""Presentation views for LLM-facing responses.

This module provides read-only view models with computed URL fields
for presenting Homebox data to LLM assistants. Views are separate from
core domain models to keep serialization logic centralized.

Design Notes:
    - Views use `from_dict()` classmethods instead of `model_validate()` because
      they perform custom transformations (truncation, URL injection, field filtering)
      that go beyond simple field mapping.
    - Views use `serialization_alias` (not `alias`) because they are output-only.
      Core domain models in models.py use `alias` for bidirectional parsing.

Usage:
    location_data = await client.get_location(token, loc_id)
    view = LocationView.from_dict(location_data)
    return view.model_dump()  # Includes computed 'url' field
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..core.config import settings

__all__ = [
    "LocationView",
    "CompactLabelView",
    "CompactItemView",
    "ParentItemView",
    "ItemView",
    "add_tree_urls",
]


class LocationView(BaseModel):
    """Read-only view for locations with computed URL."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str = ""
    item_count: int = Field(default=0, serialization_alias="itemCount")
    children: list[LocationView] = Field(default_factory=list)

    @computed_field
    @property
    def url(self) -> str:
        """Generate URL for this location."""
        return f"{settings.effective_link_base_url}/location/{self.id}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocationView:
        """Create a LocationView from an API response dictionary.

        Uses custom parsing instead of model_validate() to:
        - Recursively convert children to LocationView instances
        - Ensure computed URL field is available on serialization
        """
        # Recursively parse children
        children_data = data.get("children", [])
        children = [cls.from_dict(child) for child in children_data] if children_data else []

        # Validate required fields - log warnings but don't fail
        location_id = data.get("id") or ""
        location_name = data.get("name") or ""
        if not location_id:
            from loguru import logger

            logger.warning("LocationView.from_dict received data without id")

        return cls(
            id=location_id,
            name=location_name,
            description=data.get("description") or "",
            item_count=data.get("itemCount", 0),
            children=children,
        )


class CompactLabelView(BaseModel):
    """Minimal label view for compact item responses.

    Only includes id and name to reduce token usage while still
    allowing the LLM to work with labels without fetching full item details.
    """

    id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompactLabelView:
        """Create a CompactLabelView from an API response dictionary."""
        return cls(
            id=data.get("id") or "",
            name=data.get("name") or "",
        )


class CompactItemView(BaseModel):
    """Minimal item view for list responses (reduces token usage).

    Includes only essential fields with description truncated to 50 chars.
    Nested location also gets a URL for markdown link generation.
    Labels are included as compact views (id + name only).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str = ""  # Truncated to 50 chars
    quantity: int = 1
    asset_id: str | None = Field(default=None, serialization_alias="assetId")
    location: LocationView | None = None
    labels: list[CompactLabelView] = Field(default_factory=list)

    @computed_field
    @property
    def url(self) -> str:
        """Generate URL for this item."""
        return f"{settings.effective_link_base_url}/item/{self.id}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompactItemView:
        """Create a CompactItemView from an API response dictionary.

        Uses custom parsing instead of model_validate() to:
        - Truncate description to 50 chars for token efficiency
        - Build nested LocationView for URL generation
        - Build compact label views (id + name only)
        - Filter out unnecessary fields from the compact representation
        """
        # Build location view if present
        location_data = data.get("location")
        location_view = None
        if location_data and location_data.get("id"):
            location_view = LocationView(
                id=location_data.get("id", ""),
                name=location_data.get("name", ""),
                description="",  # Don't include description in compact view
                item_count=0,
            )

        # Build compact label views
        labels_data = data.get("labels", [])
        labels = [CompactLabelView.from_dict(lbl) for lbl in labels_data if lbl.get("id")]

        # Truncate description (50 chars is enough context for label decisions)
        description = data.get("description") or ""
        truncated_desc = description[:50] + ("..." if len(description) > 50 else "")

        # Validate required fields - log warnings but don't fail
        item_id = data.get("id") or ""
        if not item_id:
            from loguru import logger

            logger.warning("CompactItemView.from_dict received data without id")

        return cls(
            id=item_id,
            name=data.get("name") or "",
            description=truncated_desc,
            quantity=data.get("quantity", 1),
            asset_id=data.get("assetId"),
            location=location_view,
            labels=labels,
        )


class ParentItemView(BaseModel):
    """Minimal view for representing a parent item relationship.

    Only includes id and name to keep token usage low while still
    allowing the LLM to understand item hierarchies.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str

    @computed_field
    @property
    def url(self) -> str:
        """Generate URL for this parent item."""
        return f"{settings.effective_link_base_url}/item/{self.id}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParentItemView:
        """Create a ParentItemView from an API response dictionary."""
        return cls(
            id=data.get("id") or "",
            name=data.get("name") or "",
        )


class ItemView(BaseModel):
    """Full item view for detailed responses with computed URL.

    Use this when returning full item details (non-compact mode).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str = ""
    quantity: int = 1
    asset_id: str | None = Field(default=None, serialization_alias="assetId")
    location: LocationView | None = None
    parent: ParentItemView | None = None
    labels: list[dict[str, Any]] = Field(default_factory=list)
    manufacturer: str | None = None
    model_number: str | None = Field(default=None, serialization_alias="modelNumber")
    serial_number: str | None = Field(default=None, serialization_alias="serialNumber")
    purchase_price: float | None = Field(default=None, serialization_alias="purchasePrice")
    purchase_from: str | None = Field(default=None, serialization_alias="purchaseFrom")
    notes: str | None = None
    insured: bool = False

    @computed_field
    @property
    def url(self) -> str:
        """Generate URL for this item."""
        return f"{settings.effective_link_base_url}/item/{self.id}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ItemView:
        """Create an ItemView from an API response dictionary.

        Uses custom parsing instead of model_validate() to:
        - Build nested LocationView for URL generation
        - Build nested ParentItemView for parent item relationships
        - Ensure all optional fields have safe defaults
        """
        # Build location view if present
        location_data = data.get("location")
        location_view = None
        if location_data and location_data.get("id"):
            location_view = LocationView.from_dict(location_data)

        # Build parent view if present
        parent_data = data.get("parent")
        parent_view = None
        if parent_data and parent_data.get("id"):
            parent_view = ParentItemView.from_dict(parent_data)

        # Validate required fields - log warnings but don't fail
        item_id = data.get("id") or ""
        if not item_id:
            from loguru import logger

            logger.warning("ItemView.from_dict received data without id")

        return cls(
            id=item_id,
            name=data.get("name") or "",
            description=data.get("description") or "",
            quantity=data.get("quantity", 1),
            asset_id=data.get("assetId"),
            location=location_view,
            parent=parent_view,
            labels=data.get("labels", []),
            manufacturer=data.get("manufacturer"),
            model_number=data.get("modelNumber"),
            serial_number=data.get("serialNumber"),
            purchase_price=data.get("purchasePrice"),
            purchase_from=data.get("purchaseFrom"),
            notes=data.get("notes"),
            insured=data.get("insured", False),
        )


def add_tree_urls(node: dict[str, Any]) -> dict[str, Any]:
    """Recursively add URLs to tree nodes (locations and items).

    Used by get_location_tree to ensure all nodes have URLs for markdown links.
    Mutates the node in place and returns it.

    Args:
        node: Tree node with 'type' (location/item) and optional 'children' fields.

    Returns:
        Same node with 'url' field added.
    """
    base_url = settings.effective_link_base_url

    if node.get("type") == "location":
        node["url"] = f"{base_url}/location/{node.get('id')}"
    else:  # item
        node["url"] = f"{base_url}/item/{node.get('id')}"

    # Recursively process children
    for child in node.get("children", []):
        add_tree_urls(child)

    return node
