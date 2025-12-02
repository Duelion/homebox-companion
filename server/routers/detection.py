"""Detection router for AI-powered image analysis."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

from homebox_vision import (
    correct_item_with_openai,
    detect_items_from_bytes,
    encode_image_bytes_to_data_uri,
    merge_items_with_openai,
    settings,
)
from server.dependencies import get_labels_for_context, get_token, require_openai_key
from server.schemas.detection import (
    AdvancedItemDetails,
    CorrectedItemResponse,
    CorrectionResponse,
    DetectedItemResponse,
    DetectionResponse,
    MergedItemResponse,
    MergeItemsRequest,
)
from server.services import AIService

router = APIRouter(prefix="/api", tags=["Detection"])


@router.post("/detect", response_model=DetectionResponse)
async def detect_items(
    image: Annotated[UploadFile, File(description="Primary image file to analyze")],
    token: Annotated[str, Depends(get_token)],
    single_item: Annotated[bool, Form()] = False,
    extra_instructions: Annotated[str | None, Form()] = None,
    extract_extended_fields: Annotated[bool, Form()] = True,
    additional_images: Annotated[
        list[UploadFile] | None, File(description="Additional images for the same item")
    ] = None,
) -> DetectionResponse:
    """Analyze an uploaded image and detect items using OpenAI vision.

    This endpoint uses AI to identify items in photos and return structured
    data suitable for creating Homebox inventory entries.

    Args:
        image: The primary image file to analyze.
        token: Bearer token for authentication.
        single_item: If True, treat everything in the image as a single item
            (do not separate into multiple items).
        extra_instructions: Optional user hint about what's in the image
            (e.g., "the items in the photo are static grass for train models").
        extract_extended_fields: If True (default), also extract extended fields
            like manufacturer, modelNumber, serialNumber when visible in the image.
        additional_images: Optional additional images showing the same item(s)
            from different angles or showing additional details.

    Returns:
        A DetectionResponse containing the list of detected items.
    """
    additional_count = len(additional_images) if additional_images else 0
    logger.info(f"Detecting items from image: {image.filename} (+ {additional_count} additional)")
    logger.info(f"Single item mode: {single_item}, Extra instructions: {extra_instructions}")
    logger.info(f"Extract extended fields: {extract_extended_fields}")

    # Ensure OpenAI is configured
    api_key = require_openai_key()

    # Read primary image bytes
    image_bytes = await image.read()
    if not image_bytes:
        logger.warning("Empty image file received")
        raise HTTPException(status_code=400, detail="Empty image file")

    logger.debug(f"Primary image size: {len(image_bytes)} bytes")

    # Determine MIME type
    content_type = image.content_type or "image/jpeg"
    logger.debug(f"Content type: {content_type}")

    # Read additional images if provided
    additional_image_data: list[tuple[bytes, str]] = []
    if additional_images:
        for add_img in additional_images:
            add_bytes = await add_img.read()
            if add_bytes:
                add_mime = add_img.content_type or "image/jpeg"
                additional_image_data.append((add_bytes, add_mime))
                logger.debug(f"Additional image: {add_img.filename}, size: {len(add_bytes)} bytes")

    # Fetch labels for context
    labels = await get_labels_for_context(token)

    # Detect items using AI service
    try:
        logger.info("Starting OpenAI vision detection...")
        detected = await detect_items_from_bytes(
            image_bytes=image_bytes,
            api_key=api_key,
            mime_type=content_type,
            model=settings.openai_model,
            labels=labels,
            single_item=single_item,
            extra_instructions=extra_instructions,
            extract_extended_fields=extract_extended_fields,
            additional_images=additional_image_data,
        )
        logger.info(f"Detected {len(detected)} items")
        for item in detected:
            logger.debug(f"  - {item.name} (qty: {item.quantity}, labels: {item.label_ids})")
            if item.has_extended_fields():
                logger.debug(
                    f"    Extended: manufacturer={item.manufacturer}, "
                    f"model={item.model_number}, serial={item.serial_number}"
                )
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}") from e

    response = DetectionResponse(
        items=[
            DetectedItemResponse(
                name=item.name,
                quantity=item.quantity,
                description=item.description,
                label_ids=item.label_ids,
                manufacturer=item.manufacturer,
                model_number=item.model_number,
                serial_number=item.serial_number,
                purchase_price=item.purchase_price,
                purchase_from=item.purchase_from,
                notes=item.notes,
            )
            for item in detected
        ]
    )
    logger.debug(f"API Response JSON: {response.model_dump_json()}")
    return response


@router.post("/analyze-advanced")
async def analyze_item_advanced(
    images: Annotated[list[UploadFile], File(description="Images to analyze")],
    item_name: Annotated[str, Form()],
    token: Annotated[str, Depends(get_token)],
    item_description: Annotated[str | None, Form()] = None,
) -> AdvancedItemDetails:
    """Analyze multiple images to extract detailed item information.

    This endpoint is used for advanced analysis where the user wants to
    extract as much detail as possible from multiple angles of an item.

    Args:
        images: List of image files to analyze.
        item_name: The name of the item being analyzed.
        item_description: Optional initial description of the item.
        token: Bearer token for authentication.

    Returns:
        Detailed item information extracted from the images.
    """
    logger.info(f"Advanced analysis for item: {item_name}")
    logger.debug(f"Description: {item_description}")
    logger.debug(f"Number of images: {len(images) if images else 0}")

    api_key = require_openai_key()

    if not images:
        logger.warning("No images provided for analysis")
        raise HTTPException(status_code=400, detail="At least one image is required")

    # Fetch labels for context
    labels = await get_labels_for_context(token)

    # Use AI service for analysis
    ai_service = AIService(api_key=api_key, model=settings.openai_model)
    details = await ai_service.analyze_item_details(
        images=images,
        item_name=item_name,
        item_description=item_description,
        labels=labels,
    )

    return AdvancedItemDetails(
        name=details.get("name"),
        description=details.get("description"),
        serial_number=details.get("serialNumber"),
        model_number=details.get("modelNumber"),
        manufacturer=details.get("manufacturer"),
        purchase_price=details.get("purchasePrice"),
        notes=details.get("notes"),
        label_ids=details.get("labelIds"),
    )


@router.post("/merge-items", response_model=MergedItemResponse)
async def merge_items(
    request: MergeItemsRequest,
    token: Annotated[str, Depends(get_token)],
) -> MergedItemResponse:
    """Merge multiple items into a single consolidated item using AI.

    This is useful when the user wants to combine similar items
    (e.g., different grit sandpapers → "Sandpaper Assortment").

    Args:
        request: The items to merge.
        token: Bearer token for authentication.

    Returns:
        A single merged item with consolidated information.
    """
    logger.info(f"Merging {len(request.items)} items")
    for item in request.items:
        logger.debug(f"  - {item.get('name')}: {item.get('description', '')[:50]}")

    api_key = require_openai_key()

    if len(request.items) < 2:
        raise HTTPException(status_code=400, detail="At least 2 items are required to merge")

    # Fetch labels for context
    labels = await get_labels_for_context(token)

    try:
        logger.info("Calling OpenAI for item merge...")
        merged = await merge_items_with_openai(
            items=request.items,
            api_key=api_key,
            model=settings.openai_model,
            labels=labels,
        )
        logger.info(f"Merge complete: {merged.get('name')}")
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        raise HTTPException(status_code=500, detail=f"Merge failed: {e}") from e

    return MergedItemResponse(
        name=merged.get("name", "Merged Item"),
        quantity=merged.get("quantity", sum(item.get("quantity", 1) for item in request.items)),
        description=merged.get("description"),
        label_ids=merged.get("labelIds"),
    )


@router.post("/correct-item", response_model=CorrectionResponse)
async def correct_item(
    image: Annotated[UploadFile, File(description="Original image of the item")],
    current_item: Annotated[str, Form(description="JSON string of current item")],
    correction_instructions: Annotated[str, Form(description="User's correction feedback")],
    token: Annotated[str, Depends(get_token)],
) -> CorrectionResponse:
    """Correct an item based on user feedback.

    This endpoint allows users to provide feedback about a detected item,
    such as "actually these are soldering tips, not screws" or
    "these are two separate items: wire solder and paste solder".

    The AI will re-analyze the image with the user's feedback and return
    either a single corrected item or multiple items if the user indicated
    they should be split.

    Args:
        image: The original image of the item.
        current_item: JSON string of the current item data.
        correction_instructions: User's correction text explaining what's wrong.
        token: Bearer token for authentication.

    Returns:
        Corrected item(s) based on the user's feedback.
    """
    logger.info("Item correction request received")
    logger.debug(f"Correction instructions: {correction_instructions}")

    api_key = require_openai_key()

    # Parse current item from JSON string
    try:
        current_item_dict = json.loads(current_item)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON for current_item: {e}")
        raise HTTPException(status_code=400, detail="Invalid current_item JSON") from e

    logger.debug(f"Current item: {current_item_dict}")

    # Read and encode image
    image_bytes = await image.read()
    if not image_bytes:
        logger.warning("Empty image file received")
        raise HTTPException(status_code=400, detail="Empty image file")

    content_type = image.content_type or "image/jpeg"
    image_data_uri = encode_image_bytes_to_data_uri(image_bytes, content_type)

    # Fetch labels for context
    labels = await get_labels_for_context(token)

    # Call the correction function
    try:
        logger.info("Starting OpenAI item correction...")
        corrected_items = await correct_item_with_openai(
            image_data_uri=image_data_uri,
            current_item=current_item_dict,
            correction_instructions=correction_instructions,
            api_key=api_key,
            model=settings.openai_model,
            labels=labels,
        )
        logger.info(f"Correction resulted in {len(corrected_items)} item(s)")
    except Exception as e:
        logger.error(f"Item correction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Correction failed: {e}") from e

    return CorrectionResponse(
        items=[
            CorrectedItemResponse(
                name=item.get("name", "Unknown"),
                quantity=item.get("quantity", 1),
                description=item.get("description"),
                label_ids=item.get("labelIds"),
            )
            for item in corrected_items
        ],
        message=f"Corrected to {len(corrected_items)} item(s)",
    )
