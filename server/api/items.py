"""Items API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from loguru import logger

from homebox_companion import AuthenticationError, DetectedItem

from ..dependencies import get_client, get_token, validate_file_size
from ..schemas.items import BatchCreateRequest

router = APIRouter()


@router.post("/items")
async def create_items(
    request: BatchCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    """Create multiple items in Homebox.

    For each item, first creates it with basic fields, then updates it with
    any extended fields since the Homebox API only accepts extended fields
    via update, not create.
    """
    logger.info(f"Creating {len(request.items)} items")
    logger.debug(f"Request location_id: {request.location_id}")

    token = get_token(authorization)
    client = get_client()

    created: list[dict[str, Any]] = []
    errors: list[str] = []

    for item_input in request.items:
        # Use request-level location_id if item doesn't have one
        location_id = item_input.location_id or request.location_id

        logger.debug(f"Creating item: {item_input.name}")
        logger.debug(f"  location_id: {location_id}")
        logger.debug(f"  label_ids: {item_input.label_ids}")

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
            from homebox_companion.homebox import ItemCreate

            item_create = ItemCreate(
                name=detected_item.name,
                quantity=detected_item.quantity,
                description=detected_item.description,
                location_id=detected_item.location_id,
                label_ids=detected_item.label_ids,
            )
            result = await client.create_item(token, item_create)
            item_id = result.get("id")
            logger.info(f"Created item: {result.get('name')} (id: {item_id})")

            # Step 2: If there are extended fields, update the item
            if item_id and detected_item.has_extended_fields():
                extended_payload = detected_item.get_extended_fields_payload()
                if extended_payload:
                    logger.debug(f"  Updating with extended fields: {extended_payload.keys()}")
                    # Get the full item to merge with extended fields
                    full_item = await client.get_item(token, item_id)
                    # Merge extended fields into the full item data
                    update_data = {
                        "name": full_item.get("name"),
                        "description": full_item.get("description"),
                        "quantity": full_item.get("quantity"),
                        "locationId": full_item.get("location", {}).get("id"),
                        "labelIds": [
                            lbl.get("id") for lbl in full_item.get("labels", []) if lbl.get("id")
                        ],
                        **extended_payload,
                    }
                    result = await client.update_item(token, item_id, update_data)
                    logger.info("  Updated item with extended fields")

            created.append(result)
        except Exception as e:
            # Log full error details but return generic message to client
            logger.exception(f"Failed to create '{item_input.name}'")
            errors.append(f"Failed to create '{item_input.name}'")

    logger.info(f"Item creation complete: {len(created)} created, {len(errors)} failed")

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
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Upload an attachment (image) to an existing item."""
    logger.info(f"Uploading attachment to item: {item_id}")
    logger.debug(f"File: {file.filename}, content_type: {file.content_type}")

    token = get_token(authorization)
    client = get_client()

    # Validate file size (raises HTTPException if too large)
    file_bytes = await validate_file_size(file)

    filename = file.filename or "image.jpg"
    mime_type = file.content_type or "image/jpeg"

    try:
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
    except AuthenticationError as e:
        logger.exception("Auth error uploading attachment")
        raise HTTPException(status_code=401, detail="Authentication failed") from e
    except Exception as e:
        # Log full error but return generic message
        logger.exception(f"Error uploading attachment to item {item_id}")
        raise HTTPException(status_code=500, detail="Failed to upload attachment") from e

