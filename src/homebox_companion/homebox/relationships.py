"""Build Homebox item request bodies that preserve existing data.

Homebox's item PUT is a full replace in every supported version: omitted
scalars are zeroed, omitted dates cleared, custom fields missing from
``fields`` deleted, and (0.27) an omitted ``locationId`` override dropped.
"""

from typing import Any


def item_relationship_payload(
    current: dict[str, Any],
    *,
    parent_id: str | None = None,
    location_id: str | None = None,
    clear_parent: bool = False,
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
        item_relationship_payload(current, parent_id=parent_id, location_id=location_id, clear_parent=clear_parent)
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
