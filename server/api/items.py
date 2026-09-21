"""Items API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from loguru import logger

from homebox_companion import (
    DetectedItem,
    HomeboxAuthError,
    HomeboxCompanionError,
    HomeboxGateway,
    settings,
)
from homebox_companion.ai.images import compress_image_for_upload
from homebox_companion.core import HomeboxAPIError
from homebox_companion.homebox import ItemCreate

from ..dependencies import get_gateway, get_valid_tag_ids, validate_file_size
from ..schemas.items import BatchCreateRequest

router = APIRouter()


@router.get("/items")
async def list_items(
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
    location_id: str | None = Query(None, alias="location_id"),
) -> list[dict]:
    """
    List items, optionally filtered by location.

    Returns a simplified list of items suitable for selection UI.
    """
    logger.debug(f"Fetching items for location_id={location_id}")

    response = await gateway.list_items(location_id=location_id)
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
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
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

    # Fetch valid tag IDs once for the batch to validate against
    valid_tag_ids = await get_valid_tag_ids(gateway)

    for index, item_input in enumerate(request.items):
        # Resolve parent (container) ID: item-level → request-level fallback
        # In 0.26, location_id and parent_id both map to the API's parentId field
        parent_id = item_input.location_id or request.location_id or item_input.parent_id

        logger.debug(f"Creating item: {item_input.name}")
        logger.debug(f"  parent_id: {parent_id}")
        logger.debug(f"  tag_ids: {item_input.tag_ids}")

        # Validate tag_ids against Homebox to filter out invalid/stale IDs
        validated_tag_ids: list[str] | None = None
        if item_input.tag_ids:
            validated_tag_ids = [tid for tid in item_input.tag_ids if tid in valid_tag_ids]
            filtered_count = len(item_input.tag_ids) - len(validated_tag_ids)
            if filtered_count > 0:
                logger.warning(f"Filtered out {filtered_count} invalid tag ID(s) for '{item_input.name}'")

        try:
            detected_item = DetectedItem(
                name=item_input.name,
                quantity=item_input.quantity,
                description=item_input.description,
                parent_id=parent_id,  # ty: ignore[unknown-argument]
                tag_ids=validated_tag_ids if validated_tag_ids else None,  # ty: ignore[unknown-argument]
                manufacturer=item_input.manufacturer,
                model_number=item_input.model_number,  # ty: ignore[unknown-argument]
                serial_number=item_input.serial_number,  # ty: ignore[unknown-argument]
                purchase_price=item_input.purchase_price,  # ty: ignore[unknown-argument]
                purchase_from=item_input.purchase_from,  # ty: ignore[unknown-argument]
                notes=item_input.notes,
            )

            # Step 1: Create item with basic fields
            item_create = ItemCreate(
                name=detected_item.name,
                quantity=detected_item.quantity,
                description=detected_item.description or "",
                parent_id=detected_item.parent_id,  # ty: ignore[unknown-argument]
                tag_ids=detected_item.tag_ids,  # ty: ignore[unknown-argument]
            )
            result = await gateway.create_item(item_create)
            item_id = result.get("id")
            logger.info(f"Created item: {result.get('name')} (id: {item_id})")

            # Step 2: If there are extended fields or custom fields, update the item
            has_custom = bool(item_input.custom_fields)
            if item_id and (detected_item.has_extended_fields() or has_custom):
                extended_payload = detected_item.get_extended_fields_payload() or {}
                if extended_payload or has_custom:
                    logger.debug(f"  Updating with extended fields: {extended_payload.keys()}")
                    try:
                        # Get the full item to merge with extended fields
                        full_item = await gateway.get_item(item_id)
                        # Merge extended fields into the full item data
                        update_data = {
                            "name": full_item.get("name"),
                            "description": full_item.get("description"),
                            "quantity": full_item.get("quantity"),
                            "parentId": full_item.get("parent", {}).get("id"),
                            "tagIds": [tag.get("id") for tag in full_item.get("tags", []) if tag.get("id")],
                            **extended_payload,
                        }
                        # Include custom fields as typed Homebox ItemField objects
                        if item_input.custom_fields:
                            from homebox_companion.tools.vision.models import HomeboxItemField

                            update_data["fields"] = [
                                HomeboxItemField(name=name, textValue=value).model_dump(by_alias=True)
                                for name, value in item_input.custom_fields.items()
                                if value  # skip empty/null values
                            ]
                        # Preserve parentId if it was set
                        if item_input.parent_id:
                            update_data["parentId"] = item_input.parent_id
                        result = await gateway.update_item(item_id, update_data)
                        logger.info("  Updated item with extended fields")
                    except HomeboxAuthError:
                        # The initial POST succeeded. Return its identity even though
                        # enrichment failed so callers cannot mistake it for an item
                        # that is safe to create again.
                        created.append(result)
                        raise
                    except Exception as update_err:
                        # Non-auth update failures - clean up the partially created item
                        logger.warning(
                            f"Extended fields update failed for '{item_input.name}', "
                            f"cleaning up item {item_id}: {update_err}"
                        )
                        try:
                            await gateway.delete_item(item_id)
                            logger.info(f"  Cleaned up partial item {item_id}")
                        except Exception as delete_err:
                            logger.error(f"  Failed to clean up item {item_id}: {delete_err}")
                            # Deletion was not confirmed; treat the known ID as an
                            # incomplete creation rather than inviting another POST.
                            created.append(result)
                        raise update_err

            created.append(result)
        except HomeboxAuthError:
            # Auth failure means all subsequent items will also fail - abort early
            logger.error(f"Authentication failed while creating '{item_input.name}'")
            errors.append(f"Authentication failed for '{item_input.name}'")
            # Add remaining items as not attempted
            remaining = len(request.items) - index - 1
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
            assigned = await gateway.ensure_asset_ids()
            if assigned > 0:
                logger.info(f"Assigned asset IDs to {assigned} item(s)")
        except Exception as e:
            # Non-fatal - log but don't fail the request
            logger.warning(f"Failed to ensure asset IDs: {e}")

    return JSONResponse(
        content={
            "created": created,
            "errors": errors,
            "message": (f"Created {len(created)} items" + (f", {len(errors)} failed" if errors else "")),
        },
        status_code=200 if not errors else 207,  # 207 Multi-Status if partial success
    )


@router.post("/items/{item_id}/attachments")
async def upload_item_attachment(
    item_id: str,
    file: Annotated[UploadFile, File(description="Image file to upload")],
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
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
        logger.warning(f"Suspiciously small file for item {item_id}: {file.filename} ({file_size} bytes)")

    filename = file.filename or "image.jpg"
    mime_type = file.content_type or "image/jpeg"

    max_dimension, jpeg_quality = settings.image_quality_params
    file_bytes, mime_type = compress_image_for_upload(file_bytes, max_dimension, jpeg_quality)

    result = await gateway.upload_attachment(
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
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> Response:
    """Proxy attachment requests to Homebox with proper auth.

    This allows the frontend to load thumbnails without exposing auth tokens
    to the browser. The browser makes requests to this endpoint, and we
    forward them to Homebox with the proper Authorization header.
    """
    logger.debug(f"Proxying attachment request: item={item_id}, attachment={attachment_id}")

    try:
        content, content_type = await gateway.get_attachment(item_id, attachment_id)
        return Response(content=content, media_type=content_type)
    except FileNotFoundError as e:
        # Route-specific: 404 for missing attachments
        raise HTTPException(status_code=404, detail="Attachment not found") from e


@router.put("/items/{item_id}")
async def update_item(
    item_id: str,
    request: dict[str, Any],
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> dict[str, Any]:
    """Update an existing item in Homebox.

    Used to set asset ID after item creation (since asset ID cannot be set during creation).
    Fetches the full item first to merge with update data.
    """
    logger.info(f"Updating item: {item_id}")
    logger.debug(f"Update data: {request}")

    # Fetch current item to get required fields
    full_item = await gateway.get_item(item_id)

    # Build update payload with current values + updates
    update_data = {
        "name": full_item.get("name"),
        "description": full_item.get("description", ""),
        "quantity": full_item.get("quantity", 1),
        "parentId": full_item.get("parent", {}).get("id"),
        "tagIds": [tag.get("id") for tag in full_item.get("tags", []) if tag.get("id")],
    }

    # Apply requested updates (convert snake_case to camelCase for Homebox API)
    if "assetId" in request:
        update_data["assetId"] = request["assetId"]
    if "name" in request:
        update_data["name"] = request["name"]
    if "description" in request:
        update_data["description"] = request["description"]

    result = await gateway.update_item(item_id, update_data)
    logger.info(f"Successfully updated item {item_id}")
    return result


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> dict[str, str]:
    """Delete an item from Homebox.

    Used for cleanup when item creation succeeds but attachment upload fails.
    """
    logger.info(f"Deleting item: {item_id}")

    await gateway.delete_item(item_id)
    logger.info(f"Successfully deleted item {item_id}")
    return {"message": "Item deleted"}


@router.post("/items/{item_id}/print-label")
async def print_item_label(
    item_id: str,
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> dict[str, str]:
    """Trigger server-side asset label printing for an item.

    Homebox's asset label endpoint requires the item's asset ID rather than
    its entity UUID. Requires HBOX_LABEL_MAKER_PRINT_COMMAND to be configured
    on the Homebox server.
    """
    if not settings.print_enabled:
        raise HTTPException(
            status_code=403,
            detail="Label printing is not enabled on this server (HBC_PRINT_ENABLED=false).",
        )

    logger.info(f"Printing label for item: {item_id}")

    try:
        item = await gateway.get_item_typed(item_id)
        if not item.asset_id:
            raise HTTPException(
                status_code=409,
                detail="Item does not have an asset ID assigned yet.",
            )

        result = await gateway.print_label(item.asset_id)
        logger.info(
            f"Label printed for item {item_id} (asset {item.asset_id}): {result}"
        )
        return {"message": result}
    except (HomeboxCompanionError, HTTPException):
        raise
    except Exception as e:
        raise HomeboxAPIError(
            message=f"Unexpected error while printing label for item {item_id}",
            user_message=(
                "Failed to print label. Ensure HBOX_LABEL_MAKER_PRINT_COMMAND "
                "is configured on the Homebox server."
            ),
            context={"item_id": item_id},
        ) from e
