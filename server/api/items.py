"""Items API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from loguru import logger

from homebox_companion import DetectedItem, HomeboxAuthError, HomeboxClient
from homebox_companion.homebox import ItemCreate

from ..dependencies import get_client, get_token, get_valid_label_ids, validate_file_size
from ..schemas.items import BatchCreateRequest

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

    # Fetch valid label IDs once for the batch to validate against
    valid_label_ids = await get_valid_label_ids(token, client)

    for item_input in request.items:
        # Use request-level location_id if item doesn't have one
        location_id = item_input.location_id or request.location_id

        logger.debug(f"Creating item: {item_input.name}")
        logger.debug(f"  location_id: {location_id}")
        logger.debug(f"  label_ids: {item_input.label_ids}")
        logger.debug(f"  parent_id: {item_input.parent_id}")

        # Validate label_ids against Homebox to filter out invalid/stale IDs
        validated_label_ids: list[str] | None = None
        if item_input.label_ids:
            validated_label_ids = [lid for lid in item_input.label_ids if lid in valid_label_ids]
            filtered_count = len(item_input.label_ids) - len(validated_label_ids)
            if filtered_count > 0:
                logger.warning(
                    f"Filtered out {filtered_count} invalid label ID(s) for '{item_input.name}'"
                )

        detected_item = DetectedItem(
            name=item_input.name,
            quantity=item_input.quantity,
            description=item_input.description,
            location_id=location_id,
            label_ids=validated_label_ids if validated_label_ids else None,
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
                            "labelIds": [lbl.get("id") for lbl in full_item.get("labels", []) if lbl.get("id")],
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
        logger.warning(f"Suspiciously small file for item {item_id}: {file.filename} ({file_size} bytes)")

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
