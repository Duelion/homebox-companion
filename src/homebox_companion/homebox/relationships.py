"""Build the containment fields for Homebox item PUT requests."""

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
