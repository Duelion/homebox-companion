"""Data models for vision-based item detection.

Pydantic models for representing items detected by AI vision.
LiteLLM supports Pydantic models for structured output, so we define
DetectedItem as a Pydantic BaseModel for automatic validation.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, create_model

if TYPE_CHECKING:
    from ...core.persistent_settings import CustomFieldDefinition


class DetectedItem(BaseModel):
    """Structured representation for objects detected in an image.

    This class represents an item that has been identified by the AI vision
    model and can be created in Homebox. LiteLLM will validate the LLM output
    against this schema automatically.

    Extended fields (manufacturer, model_number, etc.) require an update
    after item creation since Homebox API doesn't accept them during POST.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str, Field(min_length=1, max_length=255)]
    quantity: int = Field(default=1, ge=1)
    description: Annotated[str, Field(max_length=1000)] | None = None
    location_id: str | None = Field(default=None, alias="locationId")
    tag_ids: list[str] | None = Field(default=None, alias="tagIds")

    # Extended fields (can only be set via update, not create)
    manufacturer: Annotated[str, Field(max_length=255)] | None = None
    model_number: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="modelNumber")
    serial_number: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="serialNumber")
    purchase_price: float | None = Field(default=None, gt=0, alias="purchasePrice")
    purchase_from: Annotated[str, Field(max_length=255)] | None = Field(default=None, alias="purchaseFrom")
    notes: Annotated[str, Field(max_length=1000)] | None = None

    def get_extended_fields_payload(self) -> dict[str, str | float] | None:
        """Get extended fields that require an update after item creation.

        These fields (manufacturer, modelNumber, serialNumber, purchasePrice,
        purchaseFrom, notes) cannot be set during item creation and must be
        added via a subsequent PUT request.

        Returns:
            A dictionary with extended fields if any are present, or None.
        """
        payload = self.model_dump(
            by_alias=True,
            exclude_unset=True,
            exclude_none=True,
            include={"manufacturer", "model_number", "serial_number", "purchase_price", "purchase_from", "notes"},
        )
        return payload if payload else None

    def has_extended_fields(self) -> bool:
        """Check if this item has any extended fields that need updating."""
        from ...homebox.models import has_extended_fields

        return has_extended_fields(
            self.manufacturer,
            self.model_number,
            self.serial_number,
            self.purchase_price,
            self.purchase_from,
            self.notes,
        )


class HomeboxItemField(BaseModel):
    """Typed representation of a Homebox custom field value.

    Replaces raw ``{"name": ..., "textValue": ..., "type": "text"}`` dicts
    with compile-time safety.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    text_value: str = Field(alias="textValue")
    type: str = "text"


# ---------------------------------------------------------------------------
# Dynamic model creation (cached)
# ---------------------------------------------------------------------------

# Default TypeAdapter for lists of base DetectedItem (no custom fields).
# Created once at import time to avoid repeated schema compilation.
_DEFAULT_LIST_ADAPTER: TypeAdapter[list[DetectedItem]] = TypeAdapter(list[DetectedItem])
_DEFAULT_SINGLE_ADAPTER: TypeAdapter[DetectedItem] = TypeAdapter(DetectedItem)


@lru_cache(maxsize=4)
def _build_cached_model(
    cache_key: tuple[tuple[str, str, str], ...],
) -> type[DetectedItem]:
    """Cached dynamic model factory — rebuilds only when definitions change.

    The cache key is a frozen tuple of ``(field_key, name, ai_instruction)``
    triples, making invalidation automatic: any edit to custom field
    definitions produces a new key → cache miss → new model.
    ``maxsize=4`` gracefully handles the brief window during settings updates
    where old and new configs might coexist across concurrent requests.
    """
    dynamic_fields: dict = {}
    for key, _name, instruction in cache_key:
        dynamic_fields[key] = (
            str | None,
            Field(default=None, description=instruction),
        )
    return create_model("DynamicDetectedItem", __base__=DetectedItem, **dynamic_fields)


def _to_cache_key(
    custom_field_defs: list[CustomFieldDefinition],
) -> tuple[tuple[str, str, str], ...]:
    """Convert custom field defs to a hashable cache key."""
    return tuple((cf.field_key, cf.name, cf.ai_instruction) for cf in custom_field_defs)


@lru_cache(maxsize=4)
def _build_cached_list_adapter(
    cache_key: tuple[tuple[str, str, str], ...],
) -> TypeAdapter:
    """Cached TypeAdapter[list[DynamicDetectedItem]] factory."""
    model = _build_cached_model(cache_key)
    return TypeAdapter(list[model])  # type: ignore[invalid-type-form]


@lru_cache(maxsize=4)
def _build_cached_single_adapter(
    cache_key: tuple[tuple[str, str, str], ...],
) -> TypeAdapter:
    """Cached TypeAdapter[DynamicDetectedItem] factory."""
    model = _build_cached_model(cache_key)
    return TypeAdapter(model)


def get_items_adapter(
    custom_fields: list[CustomFieldDefinition] | None,
) -> TypeAdapter:
    """Get a cached ``TypeAdapter[list[DetectedItem]]`` for the given definitions.

    Returns the static default adapter when no custom fields are configured,
    or builds and caches a dynamic one from the custom field definitions.
    """
    if not custom_fields:
        return _DEFAULT_LIST_ADAPTER
    return _build_cached_list_adapter(_to_cache_key(custom_fields))


def get_single_item_adapter(
    custom_fields: list[CustomFieldDefinition] | None,
) -> TypeAdapter:
    """Get a cached ``TypeAdapter[DetectedItem]`` for the given definitions.

    Used by the analyzer which returns a single item, not a list.
    """
    if not custom_fields:
        return _DEFAULT_SINGLE_ADAPTER
    return _build_cached_single_adapter(_to_cache_key(custom_fields))


# ---------------------------------------------------------------------------
# Custom field value extraction
# ---------------------------------------------------------------------------


def _iter_custom_values(
    item: DetectedItem,
    custom_field_defs: list[CustomFieldDefinition],
) -> Iterator[tuple[str, str]]:
    """Yield ``(display_name, value)`` pairs for populated custom fields."""
    for cf in custom_field_defs:
        value = getattr(item, cf.field_key, None)
        if value is not None:
            yield cf.name, value


def get_custom_fields_payload(
    item: DetectedItem,
    custom_field_defs: list[CustomFieldDefinition],
) -> list[HomeboxItemField] | None:
    """Extract custom field values as typed Homebox ``ItemField`` objects.

    Args:
        item: A DetectedItem instance (may be a dynamic subclass).
        custom_field_defs: The custom field definitions used to build the model.

    Returns:
        A list of HomeboxItemField instances, or None if no custom fields have values.
    """
    if not custom_field_defs:
        return None

    fields = [
        HomeboxItemField(name=name, textValue=value) for name, value in _iter_custom_values(item, custom_field_defs)
    ]
    return fields if fields else None


def get_custom_fields_dict(
    item: DetectedItem,
    custom_field_defs: list[CustomFieldDefinition],
) -> dict[str, str] | None:
    """Extract custom field values as a simple display-name → value dict.

    Suitable for API responses where Homebox ItemField format is not needed.

    Args:
        item: A DetectedItem instance (may be a dynamic subclass).
        custom_field_defs: The custom field definitions used to build the model.

    Returns:
        A dict mapping display names to string values, or None if no values.
    """
    if not custom_field_defs:
        return None

    result = dict(_iter_custom_values(item, custom_field_defs))
    return result if result else None
