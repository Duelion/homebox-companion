"""Vision tool API routes."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from loguru import logger

from homebox_companion import (
    analyze_item_details_from_images,
    correct_item_with_openai,
    detect_items_from_bytes,
    encode_image_bytes_to_data_uri,
    merge_items_with_openai,
    settings,
)

from ...dependencies import get_labels_for_context, get_token
from ...schemas.vision import (
    AdvancedItemDetails,
    CorrectedItemResponse,
    CorrectionResponse,
    DetectedItemResponse,
    DetectionResponse,
    MergedItemResponse,
    MergeItemsRequest,
)

router = APIRouter()


@router.post("/detect", response_model=DetectionResponse)
async def detect_items(
    image: Annotated[UploadFile, File(description="Primary image file to analyze")],
    authorization: Annotated[str | None, Header()] = None,
    single_item: Annotated[bool, Form()] = False,
    extra_instructions: Annotated[str | None, Form()] = None,
    extract_extended_fields: Annotated[bool, Form()] = True,
    additional_images: Annotated[
        list[UploadFile] | None, File(description="Additional images for the same item")
    ] = None,
) -> DetectionResponse:
    """Analyze an uploaded image and detect items using OpenAI vision.

    Args:
        image: The primary image file to analyze.
        authorization: Bearer token for authentication.
        single_item: If True, treat everything as a single item.
        extra_instructions: Optional user hint about what's in the image.
        extract_extended_fields: If True, also extract extended fields.
        additional_images: Optional additional images for the same item(s).
    """
    additional_count = len(additional_images) if additional_images else 0
    logger.info(f"Detecting items from image: {image.filename} (+ {additional_count} additional)")
    logger.info(f"Single item mode: {single_item}, Extra instructions: {extra_instructions}")
    logger.info(f"Extract extended fields: {extract_extended_fields}")

    # Validate auth
    token = get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HBC_OPENAI_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="HBC_OPENAI_API_KEY not configured",
        )

    # Read primary image bytes
    image_bytes = await image.read()
    if not image_bytes:
        logger.warning("Empty image file received")
        raise HTTPException(status_code=400, detail="Empty image file")

    logger.debug(f"Primary image size: {len(image_bytes)} bytes")
    content_type = image.content_type or "image/jpeg"

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
    logger.debug(f"Loaded {len(labels)} labels for context")

    # Detect items
    try:
        logger.info("Starting OpenAI vision detection...")
        detected = await detect_items_from_bytes(
            image_bytes=image_bytes,
            api_key=settings.openai_api_key,
            mime_type=content_type,
            model=settings.openai_model,
            labels=labels,
            single_item=single_item,
            extra_instructions=extra_instructions,
            extract_extended_fields=extract_extended_fields,
            additional_images=additional_image_data,
        )
        logger.info(f"Detected {len(detected)} items")
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}") from e

    return DetectionResponse(
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


@router.post("/analyze", response_model=AdvancedItemDetails)
async def analyze_item_advanced(
    images: Annotated[list[UploadFile], File(description="Images to analyze")],
    item_name: Annotated[str, Form()],
    item_description: Annotated[str | None, Form()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> AdvancedItemDetails:
    """Analyze multiple images to extract detailed item information."""
    logger.info(f"Advanced analysis for item: {item_name}")
    logger.debug(f"Description: {item_description}")
    logger.debug(f"Number of images: {len(images) if images else 0}")

    token = get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HBC_OPENAI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="HBC_OPENAI_API_KEY not configured")

    if not images:
        logger.warning("No images provided for analysis")
        raise HTTPException(status_code=400, detail="At least one image is required")

    # Convert images to data URIs
    image_data_uris = []
    for img in images:
        img_bytes = await img.read()
        if img_bytes:
            mime_type = img.content_type or "image/jpeg"
            data_uri = encode_image_bytes_to_data_uri(img_bytes, mime_type)
            image_data_uris.append(data_uri)

    if not image_data_uris:
        raise HTTPException(status_code=400, detail="No valid images provided")

    # Fetch labels for context
    labels = await get_labels_for_context(token)

    # Analyze images
    try:
        logger.info(f"Analyzing {len(image_data_uris)} images with OpenAI...")
        details = await analyze_item_details_from_images(
            image_data_uris=image_data_uris,
            item_name=item_name,
            item_description=item_description,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            labels=labels,
        )
        logger.info("Analysis complete")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") from e

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


@router.post("/merge", response_model=MergedItemResponse)
async def merge_items(
    request: MergeItemsRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> MergedItemResponse:
    """Merge multiple items into a single consolidated item using AI."""
    logger.info(f"Merging {len(request.items)} items")

    token = get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HBC_OPENAI_API_KEY not configured")
        raise HTTPException(status_code=500, detail="HBC_OPENAI_API_KEY not configured")

    if len(request.items) < 2:
        raise HTTPException(status_code=400, detail="At least 2 items are required to merge")

    # Fetch labels for context
    labels = await get_labels_for_context(token)

    try:
        logger.info("Calling OpenAI for item merge...")
        merged = await merge_items_with_openai(
            items=request.items,
            api_key=settings.openai_api_key,
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


@router.post("/correct", response_model=CorrectionResponse)
async def correct_item(
    image: Annotated[UploadFile, File(description="Original image of the item")],
    current_item: Annotated[str, Form(description="JSON string of current item")],
    correction_instructions: Annotated[str, Form(description="User's correction feedback")],
    authorization: Annotated[str | None, Header()] = None,
) -> CorrectionResponse:
    """Correct an item based on user feedback.

    This endpoint allows users to provide feedback about a detected item,
    and the AI will re-analyze with the feedback.
    """
    logger.info("Item correction request received")
    logger.debug(f"Correction instructions: {correction_instructions}")

    token = get_token(authorization)

    if not settings.openai_api_key:
        logger.error("HBC_OPENAI_API_KEY not configured")
        raise HTTPException(
            status_code=500,
            detail="HBC_OPENAI_API_KEY not configured",
        )

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
    logger.debug(f"Loaded {len(labels)} labels for context")

    # Call the correction function
    try:
        logger.info("Starting OpenAI item correction...")
        corrected_items = await correct_item_with_openai(
            image_data_uri=image_data_uri,
            current_item=current_item_dict,
            correction_instructions=correction_instructions,
            api_key=settings.openai_api_key,
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

