"""Items API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from loguru import logger

from homebox_companion import DetectedItem, HomeboxAuthError, HomeboxClient
from homebox_companion.homebox import ItemCreate
from homebox_companion.services.duplicate_detector import DuplicateDetector

from ..dependencies import get_client, get_duplicate_detector, get_token, validate_file_size
from ..schemas.items import (
    BatchCreateRequest,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    DuplicateIndexRebuildResponse,
    DuplicateIndexStatus,
    DuplicateMatch,
    ExistingItemInfo,
    MergeItemRequest,
    MergeItemResponse,
)

router = APIRouter()


@router.get("/items")
async def list_items(
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
    location_id: str | None = Query(None, alias="location_id"),
) -> list[dict]:
    """
    List items, optionally filtered by location.

    Returns a simplified list of items suitable for selection UI.
    """
    logger.debug(f"Fetching items for location_id={location_id}")

    response = await client.list_items(token, location_id=location_id)
    items = response.get("items", [])

    # Return simplified item data
    result = [
        {
            "id": item["id"],
            "name": item["name"],
            "quantity": item.get("quantity", 1),
            "thumbnailId": item.get("thumbnailId"),
        }
        for item in items
    ]

    logger.debug(f"Found {len(result)} items")
    return result


@router.post("/items")
async def create_items(
    request: BatchCreateRequest,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
    detector: Annotated[DuplicateDetector, Depends(get_duplicate_detector)],
) -> JSONResponse:
    """Create multiple items in Homebox.

    For each item, first creates it with basic fields, then updates it with
    any extended fields since the Homebox API only accepts extended fields
    via update, not create.
    """
    logger.info(f"Creating {len(request.items)} items")
    logger.debug(f"Request location_id: {request.location_id}")

    created: list[dict[str, Any]] = []
    errors: list[str] = []

    for item_input in request.items:
        # Use request-level location_id if item doesn't have one
        location_id = item_input.location_id or request.location_id

        logger.debug(f"Creating item: {item_input.name}")
        logger.debug(f"  location_id: {location_id}")
        logger.debug(f"  label_ids: {item_input.label_ids}")
        logger.debug(f"  parent_id: {item_input.parent_id}")

        detected_item = DetectedItem(
            name=item_input.name,
            quantity=item_input.quantity,
            description=item_input.description,
            location_id=location_id,
            label_ids=item_input.label_ids,
            manufacturer=item_input.manufacturer,
            model_number=item_input.model_number,
            serial_number=item_input.serial_number,
            purchase_price=item_input.purchase_price,
            purchase_from=item_input.purchase_from,
            notes=item_input.notes,
        )

        try:
            # Step 1: Create item with basic fields
            item_create = ItemCreate(
                name=detected_item.name,
                quantity=detected_item.quantity,
                description=detected_item.description or "",
                location_id=detected_item.location_id,
                label_ids=detected_item.label_ids,
                parent_id=item_input.parent_id,  # Include parent_id for sub-items
            )
            result = await client.create_item(token, item_create)
            item_id = result.get("id")
            logger.info(f"Created item: {result.get('name')} (id: {item_id})")

            # Step 2: If there are extended fields, update the item
            if item_id and detected_item.has_extended_fields():
                extended_payload = detected_item.get_extended_fields_payload()
                if extended_payload:
                    logger.debug(f"  Updating with extended fields: {extended_payload.keys()}")
                    try:
                        # Get the full item to merge with extended fields
                        full_item = await client.get_item(token, item_id)
                        # Merge extended fields into the full item data
                        update_data = {
                            "name": full_item.get("name"),
                            "description": full_item.get("description"),
                            "quantity": full_item.get("quantity"),
                            "locationId": full_item.get("location", {}).get("id"),
                            "labelIds": [
                                lbl.get("id")
                                for lbl in full_item.get("labels", [])
                                if lbl.get("id")
                            ],
                            **extended_payload,
                        }
                        # Preserve parentId if it was set
                        if item_input.parent_id:
                            update_data["parentId"] = item_input.parent_id
                        result = await client.update_item(token, item_id, update_data)
                        logger.info("  Updated item with extended fields")
                    except HomeboxAuthError:
                        # Auth failure during update - don't delete the item!
                        # The item was created successfully, user just needs fresh token.
                        # Re-raise to trigger the outer auth handler.
                        raise
                    except Exception as update_err:
                        # Non-auth update failures - clean up the partially created item
                        logger.warning(
                            f"Extended fields update failed for '{item_input.name}', "
                            f"cleaning up item {item_id}: {update_err}"
                        )
                        try:
                            await client.delete_item(token, item_id)
                            logger.info(f"  Cleaned up partial item {item_id}")
                        except Exception as delete_err:
                            logger.error(f"  Failed to clean up item {item_id}: {delete_err}")
                        raise update_err

            created.append(result)
        except HomeboxAuthError:
            # Auth failure means all subsequent items will also fail - abort early
            logger.error(f"Authentication failed while creating '{item_input.name}'")
            errors.append(f"Authentication failed for '{item_input.name}'")
            # Add remaining items as not attempted
            remaining = len(request.items) - len(created) - len(errors)
            if remaining > 0:
                errors.append(f"{remaining} more item(s) not attempted due to auth failure")
            break
        except Exception as e:
            # Log full error details and include error type in response
            logger.exception(f"Failed to create '{item_input.name}'")
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else "Unknown error"
            # Truncate long error messages for the response
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            errors.append(f"Failed to create '{item_input.name}': [{error_type}] {error_msg}")

    logger.info(f"Item creation complete: {len(created)} created, {len(errors)} failed")

    # After all items created, ensure asset IDs are assigned
    if created:
        try:
            assigned = await client.ensure_asset_ids(token)
            if assigned > 0:
                logger.info(f"Assigned asset IDs to {assigned} item(s)")
        except Exception as e:
            # Non-fatal - log but don't fail the request
            logger.warning(f"Failed to ensure asset IDs: {e}")

        # Add created items to duplicate detection index (incremental update)
        items_added = 0
        for item in created:
            if detector.add_item_to_index(item):
                items_added += 1
        if items_added > 0:
            detector.save()  # Persist changes
            logger.debug(f"Added {items_added} item(s) to duplicate index")

    return JSONResponse(
        content={
            "created": created,
            "errors": errors,
            "message": (
                f"Created {len(created)} items" + (f", {len(errors)} failed" if errors else "")
            ),
        },
        status_code=200 if not errors else 207,  # 207 Multi-Status if partial success
    )


@router.post("/items/{item_id}/attachments")
async def upload_item_attachment(
    item_id: str,
    file: Annotated[UploadFile, File(description="Image file to upload")],
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> dict[str, Any]:
    """Upload an attachment (image) to an existing item."""
    logger.info(f"Uploading attachment to item: {item_id}")
    logger.debug(f"File: {file.filename}, content_type: {file.content_type}")

    # Validate file size (raises HTTPException if too large)
    file_bytes = await validate_file_size(file)

    # Log file size for diagnostics - helps identify empty/corrupted uploads
    file_size = len(file_bytes)
    logger.debug(f"Received file: {file.filename}, size: {file_size:,} bytes")
    if file_size == 0:
        logger.warning(f"Empty file received for item {item_id}: {file.filename}")
    elif file_size < 1000:
        logger.warning(
            f"Suspiciously small file for item {item_id}: {file.filename} ({file_size} bytes)"
        )

    filename = file.filename or "image.jpg"
    mime_type = file.content_type or "image/jpeg"

    result = await client.upload_attachment(
        token=token,
        item_id=item_id,
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type,
        attachment_type="photo",
    )
    logger.info(f"Successfully uploaded attachment to item {item_id}")
    return result


@router.get("/items/{item_id}/attachments/{attachment_id}")
async def get_item_attachment(
    item_id: str,
    attachment_id: str,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> Response:
    """Proxy attachment requests to Homebox with proper auth.

    This allows the frontend to load thumbnails without exposing auth tokens
    to the browser. The browser makes requests to this endpoint, and we
    forward them to Homebox with the proper Authorization header.
    """
    logger.debug(f"Proxying attachment request: item={item_id}, attachment={attachment_id}")

    try:
        content, content_type = await client.get_attachment(token, item_id, attachment_id)
        return Response(content=content, media_type=content_type)
    except FileNotFoundError as e:
        # Route-specific: 404 for missing attachments
        raise HTTPException(status_code=404, detail="Attachment not found") from e


@router.post("/items/check-duplicates", response_model=DuplicateCheckResponse)
async def check_duplicates(
    request: DuplicateCheckRequest,
    token: Annotated[str, Depends(get_token)],
    detector: Annotated[DuplicateDetector, Depends(get_duplicate_detector)],
) -> DuplicateCheckResponse:
    """Check for potential duplicate items using multiple strategies.

    This endpoint compares items against existing items in Homebox using:
    1. Serial number matching (exact, high confidence)
    2. Manufacturer + Model matching (exact, high confidence)
    3. Fuzzy name matching (similarity threshold, medium confidence)

    Uses the shared duplicate detection index which is:
    - Persisted to disk (survives restarts)
    - Incrementally updated when items are created
    - Differential updates on startup (only fetches new items)

    Use this before creating items to warn users about possible duplicates.
    """
    logger.info(f"Checking {len(request.items)} items for duplicates")

    # Convert request items to dicts for the detector (include all matching fields)
    items_to_check = [
        {
            "name": item.name,
            "serial_number": item.serial_number,
            "manufacturer": item.manufacturer,
            "model_number": item.model_number,
        }
        for item in request.items
    ]

    # Count items with checkable data
    items_with_serial = sum(1 for item in items_to_check if item.get("serial_number"))
    items_with_model = sum(
        1 for item in items_to_check
        if item.get("manufacturer") and item.get("model_number")
    )
    items_with_name = sum(1 for item in items_to_check if len(item.get("name", "")) >= 5)

    logger.debug(
        f"Items to check: {items_with_serial} with serial, "
        f"{items_with_model} with manufacturer+model, {items_with_name} with names"
    )

    # Run duplicate detection (uses shared index with auto-load)
    matches = await detector.find_duplicates(token, items_to_check)

    # Convert to response schema
    duplicates = [
        DuplicateMatch(
            item_index=match.item_index,
            item_name=match.item_name,
            match_type=match.match_type.value,  # Enum to string
            match_value=match.match_value,
            confidence=match.confidence,
            similarity_score=match.similarity_score,
            existing_item=ExistingItemInfo(
                id=match.existing_item.id,
                name=match.existing_item.name,
                serial_number=match.existing_item.serial_number,
                location_id=match.existing_item.location_id,
                location_name=match.existing_item.location_name,
                manufacturer=match.existing_item.manufacturer,
                model_number=match.existing_item.model_number,
            ),
        )
        for match in matches
    ]

    message = (
        f"Found {len(duplicates)} potential duplicate(s)"
        if duplicates
        else "No duplicates found"
    )

    logger.info(message)
    return DuplicateCheckResponse(
        duplicates=duplicates,
        checked_count=len(items_to_check),
        message=message,
    )


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> dict[str, str]:
    """Delete an item from Homebox.

    Used for cleanup when item creation succeeds but attachment upload fails.
    """
    logger.info(f"Deleting item: {item_id}")

    await client.delete_item(token, item_id)
    logger.info(f"Successfully deleted item {item_id}")
    return {"message": "Item deleted"}


# =============================================================================
# MERGE ITEM (Update existing on duplicate)
# =============================================================================


@router.post("/items/{item_id}/merge", response_model=MergeItemResponse)
async def merge_item(
    item_id: str,
    request: MergeItemRequest,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> MergeItemResponse:
    """Merge new data into an existing item (additive-only).

    This endpoint updates an existing item with new data, but ONLY fills in
    fields that are currently empty. Existing values are never overwritten.

    Use this when a duplicate is detected and the user chooses to update
    the existing item rather than create a new one.

    The exclude_field parameter prevents updating the field that caused the
    duplicate match:
    - 'serial_number': Skip serial_number field
    - 'manufacturer_model': Skip both manufacturer AND model_number
    - 'name': Skip name field

    Photos should be uploaded separately using POST /items/{item_id}/attachments.
    """
    logger.info(f"Merging data into item {item_id}")
    logger.debug(f"Exclude field: {request.exclude_field}")

    # Fetch the existing item
    try:
        existing = await client.get_item(token, item_id)
    except FileNotFoundError as e:
        logger.warning(f"Item {item_id} not found for merge")
        raise HTTPException(
            status_code=404,
            detail=f"Item {item_id} not found. It may have been deleted.",
        ) from e

    # Determine which fields to exclude
    excluded_fields: set[str] = set()
    if request.exclude_field:
        if request.exclude_field == "manufacturer_model":
            excluded_fields.add("manufacturer")
            excluded_fields.add("model_number")
        else:
            excluded_fields.add(request.exclude_field)

    # Helper to check if existing field is "empty" (should be filled)
    def is_empty(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, (list, dict)) and not value:
            return True
        # Treat numeric 0 as empty for price fields (not a real price)
        if isinstance(value, (int, float)) and value == 0:
            return True
        return False

    # Build the update payload, tracking what we update
    fields_updated: list[str] = []
    fields_skipped: list[str] = []

    # Start with ALL fields from existing item to preserve them
    # Homebox's PUT replaces fields, so we must include everything
    update_data: dict[str, Any] = {
        # Required base fields
        "name": existing.get("name"),
        "description": existing.get("description", ""),
        "quantity": existing.get("quantity", 1),
        "locationId": existing.get("location", {}).get("id"),
        "labelIds": [
            lbl.get("id") for lbl in existing.get("labels", []) if lbl.get("id")
        ],
        # Extended fields - MUST include existing values to preserve them
        "manufacturer": existing.get("manufacturer"),
        "modelNumber": existing.get("modelNumber"),
        "serialNumber": existing.get("serialNumber"),
        "purchasePrice": existing.get("purchasePrice"),
        "purchaseFrom": existing.get("purchaseFrom"),
        "notes": existing.get("notes"),
    }

    # Map of request field -> (API field name, existing value)
    field_mappings = {
        "name": ("name", existing.get("name")),
        "description": ("description", existing.get("description")),
        "manufacturer": ("manufacturer", existing.get("manufacturer")),
        "model_number": ("modelNumber", existing.get("modelNumber")),
        "serial_number": ("serialNumber", existing.get("serialNumber")),
        "purchase_price": ("purchasePrice", existing.get("purchasePrice")),
        "purchase_from": ("purchaseFrom", existing.get("purchaseFrom")),
        "notes": ("notes", existing.get("notes")),
    }

    # Process each field - only UPDATE if conditions are met
    for req_field, (api_field, existing_value) in field_mappings.items():
        new_value = getattr(request, req_field, None)

        # 1. Companion has no meaningful value - keep Homebox (don't erase)
        if new_value is None or is_empty(new_value):
            # No meaningful new value provided (None, empty string, 0, etc.)
            # Keep existing value - don't populate with defaults
            continue

        # 2. Values are identical - no change needed (includes match field case)
        if new_value == existing_value:
            if req_field in excluded_fields:
                fields_skipped.append(f"{req_field} (match field - identical)")
            else:
                fields_skipped.append(f"{req_field} (identical)")
            continue

        # 3. Match field but values are DIFFERENT - this means index may be stale
        #    or Homebox was manually edited. Companion value should be used.
        #    (If they truly matched, step 2 would have caught it)
        if req_field in excluded_fields:
            logger.info(
                f"  Match field {req_field} has different values! "
                f"Homebox='{existing_value}' Companion='{new_value}' - updating"
            )

        # 4. Companion has real value different from Homebox - update
        # This handles empty Homebox, incorrect Homebox, AND stale match fields
        if not is_empty(existing_value):
            logger.debug(f"  Overwriting {req_field}: '{existing_value}' -> '{new_value}'")
        update_data[api_field] = new_value
        fields_updated.append(req_field)
        logger.debug(f"  Updating {req_field}: {new_value}")

    # Handle labels specially - append new labels to existing
    if request.label_ids:
        existing_label_ids = set(update_data.get("labelIds", []))
        new_label_ids = set(request.label_ids)
        labels_to_add = new_label_ids - existing_label_ids

        if labels_to_add:
            update_data["labelIds"] = list(existing_label_ids | new_label_ids)
            fields_updated.append(f"label_ids (+{len(labels_to_add)} new)")
            logger.debug(f"  Adding {len(labels_to_add)} new labels")
        else:
            fields_skipped.append("label_ids (all already present)")

    # Perform the update
    try:
        result = await client.update_item(token, item_id, update_data)
        logger.info(
            f"Merged item {item_id}: {len(fields_updated)} updated, "
            f"{len(fields_skipped)} skipped"
        )
    except Exception as e:
        logger.error(f"Failed to merge item {item_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update item: {e}",
        ) from e

    # Build response message
    if fields_updated:
        message = f"Updated {len(fields_updated)} field(s): {', '.join(fields_updated)}"
    else:
        message = "No fields updated (all already had values or were excluded)"

    return MergeItemResponse(
        id=result.get("id", item_id),
        name=result.get("name", existing.get("name", "")),
        fields_updated=fields_updated,
        fields_skipped=fields_skipped,
        message=message,
    )


# =============================================================================
# DUPLICATE INDEX MANAGEMENT
# =============================================================================


@router.get("/items/duplicate-index/status", response_model=DuplicateIndexStatus)
async def get_duplicate_index_status(
    detector: Annotated[DuplicateDetector, Depends(get_duplicate_detector)],
) -> DuplicateIndexStatus:
    """Get the current status of the duplicate detection index.

    Returns information about when the index was last built/updated,
    how many items are indexed, and whether it's currently loaded.
    """
    status = detector.get_status()
    return DuplicateIndexStatus(
        last_build_time=status.last_build_time,
        last_update_time=status.last_update_time,
        total_items_indexed=status.total_items_indexed,
        items_with_serials=status.items_with_serials,
        items_with_model=status.items_with_model,
        highest_asset_id=status.highest_asset_id,
        is_loaded=status.is_loaded,
    )


@router.post("/items/duplicate-index/rebuild", response_model=DuplicateIndexRebuildResponse)
async def rebuild_duplicate_index(
    token: Annotated[str, Depends(get_token)],
    detector: Annotated[DuplicateDetector, Depends(get_duplicate_detector)],
) -> DuplicateIndexRebuildResponse:
    """Rebuild the duplicate detection index from scratch.

    This fetches ALL items from Homebox and rebuilds the serial number index.
    Use this if:
    - Items were added/modified outside of HomeBox-Companion
    - The index appears out of sync
    - You want to ensure complete accuracy

    Note: For large inventories, this may take several seconds as it needs
    to fetch details for each item to get serial numbers.
    """
    logger.info("Starting duplicate index rebuild (manual trigger)")

    try:
        status = await detector.rebuild_index(token)
    except AuthenticationError as e:
        logger.warning(f"Authentication failed during index rebuild: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Please log in to Homebox first.",
        ) from e
    except RuntimeError as e:
        logger.error(f"Index rebuild failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to rebuild index: {e}",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error during index rebuild")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error rebuilding index: {type(e).__name__}: {e}",
        ) from e

    return DuplicateIndexRebuildResponse(
        status=DuplicateIndexStatus(
            last_build_time=status.last_build_time,
            last_update_time=status.last_update_time,
            total_items_indexed=status.total_items_indexed,
            items_with_serials=status.items_with_serials,
            items_with_model=status.items_with_model,
            highest_asset_id=status.highest_asset_id,
            is_loaded=status.is_loaded,
        ),
        message=(
            f"Index rebuilt: {status.items_with_serials} serials, "
            f"{status.items_with_model} manufacturer+model pairs indexed"
        ),
    )
