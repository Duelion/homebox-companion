"""Build Homebox item request bodies that preserve existing data.

Homebox's item PUT is a full replace in every supported version: omitted
scalars are zeroed, omitted dates cleared, custom fields missing from
``fields`` deleted, and (0.27) an omitted ``locationId`` override dropped.
"""

import re
from collections.abc import Awaitable, Callable
from typing import Any


def item_relationship_payload(
    current: dict[str, Any],
    *,
    parent_id: str | None = None,
    location_id: str | None = None,
    clear_parent: bool = False,
    location_override_id: str | None = None,
    clear_location_override: bool = False,
) -> dict[str, Any]:
    """Preserve an existing explicit location only while its parent is unchanged.

    ``location_id`` is the legacy move operation: it names the new parent
    location. Homebox's own ``locationId`` is a sparse override for an item
    nested under another item, not the resolved ``location.id`` read field.
    """
    current_parent = current.get("parent") or {}
    existing_parent_id = current_parent.get("id")

    if clear_parent:
        selected_parent_id = None
    elif parent_id is not None:
        selected_parent_id = parent_id
    elif location_id is not None:
        selected_parent_id = location_id
    else:
        selected_parent_id = existing_parent_id

    payload: dict[str, Any] = {"parentId": selected_parent_id}
    if selected_parent_id == existing_parent_id and not clear_parent:
        explicit_location_id = current.get("locationId")
        if explicit_location_id is not None:
            payload["locationId"] = explicit_location_id
    if location_override_id is not None:
        payload["locationId"] = location_override_id
    elif clear_location_override:
        payload.pop("locationId", None)
    return payload


# Writable EntityUpdate scalars that GET /v1/entities/{id} returns under the same name.
_ROUND_TRIP_FIELDS = (
    "name",
    "description",
    "quantity",
    "assetId",
    "insured",
    "archived",
    "syncChildEntityLocations",
    "serialNumber",
    "modelNumber",
    "manufacturer",
    "lifetimeWarranty",
    "warrantyExpires",
    "warrantyDetails",
    "purchaseDate",
    "purchaseFrom",
    "purchasePrice",
    "soldDate",
    "soldTo",
    "soldPrice",
    "soldNotes",
    "notes",
)
_FIELD_KEYS = ("id", "type", "name", "textValue", "numberValue", "booleanValue")


def item_update_payload(
    current: dict[str, Any],
    *,
    parent_id: str | None = None,
    location_id: str | None = None,
    clear_parent: bool = False,
    location_override_id: str | None = None,
    clear_location_override: bool = False,
) -> dict[str, Any]:
    """Return a PUT body that keeps every writable field of ``current``.

    ``current`` must be a detail response (GET /v1/entities/{id}). Callers
    overlay their changes on the result; relationship changes go through the
    keyword arguments, with the same semantics as :func:`item_relationship_payload`.
    """
    payload: dict[str, Any] = {key: current[key] for key in _ROUND_TRIP_FIELDS if key in current}
    if current.get("id"):
        payload["id"] = current["id"]
    payload["tagIds"] = [tag["id"] for tag in current.get("tags") or [] if tag.get("id")]
    payload["fields"] = [
        {key: field[key] for key in _FIELD_KEYS if key in field} for field in current.get("fields") or []
    ]
    payload.update(
        item_relationship_payload(
            current,
            parent_id=parent_id,
            location_id=location_id,
            clear_parent=clear_parent,
            location_override_id=location_override_id,
            clear_location_override=clear_location_override,
        )
    )
    return payload


def location_override_for_parent(parent: dict[str, Any], selected_location_id: str) -> str | None:
    """Return the ``locationId`` that keeps a new child of ``parent`` in the selected location.

    Homebox resolves a child's location by walking its parent chain to the first
    location, ignoring overrides along the way. A parent item that has its own
    override therefore does not pass that location on, so its children need one
    too. Parents without an override pass on their location, and pinning one
    would stop the child following its container when it moves.
    """
    entity_type = parent.get("entityType")
    if not isinstance(entity_type, dict) or entity_type.get("isLocation") is not False:
        return None
    if not parent.get("locationId"):
        return None
    return selected_location_id


def validate_placement_changes(
    *,
    parent_id: str | None = None,
    location_id: str | None = None,
    clear_parent: bool = False,
    location_override_id: str | None = None,
    clear_location_override: bool = False,
) -> None:
    """Validate legacy and explicit placement operations before any mutation."""
    if sum((parent_id is not None, location_id is not None, clear_parent)) > 1:
        raise ValueError("Pass only one of parent_id, location_id or clear_parent")
    if location_override_id is not None and clear_location_override:
        raise ValueError("location_override_id conflicts with clear_location_override")
    if (location_override_id is not None or clear_location_override) and (location_id is not None or clear_parent):
        raise ValueError("Physical location override controls conflict with location_id and clear_parent")


async def preflight_item_placement(
    current: dict[str, Any],
    *,
    item_id: str,
    get_entity: Callable[[str], Awaitable[dict[str, Any]]],
    get_version: Callable[[], Awaitable[str | None]],
    parent_id: str | None = None,
    location_id: str | None = None,
    clear_parent: bool = False,
    location_override_id: str | None = None,
    clear_location_override: bool = False,
) -> None:
    """Share target and version validation between tool and direct updates."""
    validate_placement_changes(
        parent_id=parent_id,
        location_id=location_id,
        clear_parent=clear_parent,
        location_override_id=location_override_id,
        clear_location_override=clear_location_override,
    )
    explicit = location_override_id is not None or clear_location_override
    if explicit:
        try:
            version = await get_version()
            match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$", version or "")
            supported = bool(match and tuple(map(int, match.groups())) >= (0, 27, 0))
        except Exception:
            supported = False
        if not supported:
            raise ValueError("Physical location override controls require a recognized Homebox version 0.27.0 or newer")
    effective_parent = parent_id or (current.get("parent") or {}).get("id")
    if parent_id == item_id:
        raise ValueError("An item cannot be its own parent")
    if explicit:
        if not effective_parent:
            raise ValueError("Physical location overrides require a parent item")
        parent = await get_entity(effective_parent)
        if (parent.get("entityType") or {}).get("isLocation") is not False:
            raise ValueError("parent_id must identify an item")
    target_location = location_override_id or location_id
    if target_location and explicit:
        location = await get_entity(target_location)
        if (location.get("entityType") or {}).get("isLocation") is not True:
            raise ValueError("Location target must identify a location")
