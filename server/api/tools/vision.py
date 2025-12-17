"""Vision tool API routes."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

from homebox_companion import (
    CapabilityNotSupportedError,
    JSONRepairError,
    LLMError,
    ModelNotAllowedError,
    analyze_item_details_from_images,
    correct_item_with_openai,
    detect_items_from_bytes,
    encode_compressed_image_to_base64,
    encode_image_bytes_to_data_uri,
    merge_items_with_openai,
    settings,
)

from ...dependencies import (
    VisionContext,
    get_vision_context,
    validate_file_size,
    validate_files_size,
)
from ...schemas.vision import (
    AdvancedItemDetails,
    BatchDetectionResponse,
    BatchDetectionResult,
    CompressedImage,
    CorrectedItemResponse,
    CorrectionResponse,
    DetectedItemResponse,
    DetectionResponse,
    MergedItemResponse,
    MergeItemsRequest,
)

router = APIRouter()


def _llm_error_to_http(e: Exception) -> HTTPException:
    """Convert LLM exceptions to appropriate HTTP exceptions.

    Args:
        e: The exception to convert.

    Returns:
        HTTPException with appropriate status code and detail message.
    """
    if isinstance(e, ModelNotAllowedError):
        return HTTPException(
            status_code=400,
            detail=str(e),
        )
    if isinstance(e, CapabilityNotSupportedError):
        return HTTPException(
            status_code=400,
            detail=str(e),
        )
    if isinstance(e, JSONRepairError):
        return HTTPException(
            status_code=502,
            detail=f"AI returned invalid response that could not be repaired: {e}",
        )
    if isinstance(e, LLMError):
        return HTTPException(
            status_code=502,
            detail=f"LLM service error: {e}",
        )
    # Generic fallback
    return HTTPException(
        status_code=500,
        detail=f"Detection failed: {e}",
    )


def filter_default_label(label_ids: list[str] | None, default_label_id: str | None) -> list[str]:
    """Filter out the default label from AI-suggested labels.

    The frontend auto-adds the default label, so we remove it from AI suggestions
    to avoid the AI duplicating what the frontend will add anyway.

    Args:
        label_ids: List of label IDs suggested by the AI.
        default_label_id: The default label ID to filter out.

    Returns:
        Filtered list of label IDs.
    """
    if not label_ids:
        return []
    if not default_label_id:
        return label_ids
    return [lid for lid in label_ids if lid != default_label_id]


@router.post("/detect", response_model=DetectionResponse)
async def detect_items(
    image: Annotated[UploadFile, File(description="Primary image file to analyze")],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    single_item: Annotated[bool, Form()] = False,
    extra_instructions: Annotated[str | None, Form()] = None,
    extract_extended_fields: Annotated[bool, Form()] = True,
    additional_images: Annotated[
        list[UploadFile] | None, File(description="Additional images for the same item")
    ] = None,
) -> DetectionResponse:
    """Analyze an uploaded image and detect items using LLM vision.

    Args:
        image: The primary image file to analyze.
        ctx: Vision context with auth token, labels, and preferences.
        single_item: If True, treat everything as a single item.
        extra_instructions: Optional user hint about what's in the image.
        extract_extended_fields: If True, also extract extended fields.
        additional_images: Optional additional images for the same item(s).
    """
    additional_count = len(additional_images) if additional_images else 0
    logger.info(f"Detecting items from image: {image.filename} (+ {additional_count} additional)")
    logger.info(f"Single item mode: {single_item}, Extra instructions: {extra_instructions}")
    logger.info(f"Extract extended fields: {extract_extended_fields}")

    if not settings.effective_llm_api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Set HBC_LLM_API_KEY or HBC_OPENAI_API_KEY.",
        )

    # Read and validate primary image
    image_bytes = await validate_file_size(image)
    logger.debug(f"Primary image size: {len(image_bytes)} bytes")
    content_type = image.content_type or "image/jpeg"

    # Read additional images if provided (with size validation)
    additional_image_data: list[tuple[bytes, str]] = []
    if additional_images:
        for add_img in additional_images:
            add_bytes = await validate_file_size(add_img)
            add_mime = add_img.content_type or "image/jpeg"
            additional_image_data.append((add_bytes, add_mime))
            logger.debug(f"Additional image: {add_img.filename}, size: {len(add_bytes)} bytes")

    logger.debug(f"Loaded {len(ctx.labels)} labels for context")

    # Get image quality settings
    max_dimension, jpeg_quality = settings.image_quality_params

    # Run AI detection and image compression in parallel
    async def compress_all_images() -> list[CompressedImage]:
        """Compress all images (primary + additional) for Homebox upload."""
        all_images_to_compress = [(image_bytes, content_type)] + additional_image_data
        compressed = []

        for img_bytes, _ in all_images_to_compress:
            # Run compression in executor to avoid blocking
            base64_data, mime = await asyncio.to_thread(
                encode_compressed_image_to_base64,
                img_bytes,
                max_dimension,
                jpeg_quality
            )
            compressed.append(CompressedImage(data=base64_data, mime_type=mime))

        return compressed

    # Detect items
    try:
        logger.info("Starting LLM vision detection and image compression...")

        # Run detection and compression in parallel
        detection_task = detect_items_from_bytes(
            image_bytes=image_bytes,
            api_key=settings.effective_llm_api_key,
            mime_type=content_type,
            model=settings.effective_llm_model,
            labels=ctx.labels,
            single_item=single_item,
            extra_instructions=extra_instructions,
            extract_extended_fields=extract_extended_fields,
            additional_images=additional_image_data,
            field_preferences=ctx.field_preferences,
            output_language=ctx.output_language,
        )
        compression_task = compress_all_images()

        detected, compressed_images = await asyncio.gather(detection_task, compression_task)

        logger.info(f"Detected {len(detected)} items, compressed {len(compressed_images)} images")
    except (ModelNotAllowedError, CapabilityNotSupportedError, JSONRepairError, LLMError) as e:
        logger.error(f"Detection failed: {e}")
        raise _llm_error_to_http(e) from e
    except Exception as e:
        logger.exception("Detection failed unexpectedly")
        raise HTTPException(status_code=500, detail="Detection failed") from e

    # Filter out default label from AI suggestions (frontend will auto-add it)
    return DetectionResponse(
        items=[
            DetectedItemResponse(
                name=item.name,
                quantity=item.quantity,
                description=item.description,
                label_ids=filter_default_label(item.label_ids, ctx.default_label_id),
                manufacturer=item.manufacturer,
                model_number=item.model_number,
                serial_number=item.serial_number,
                purchase_price=item.purchase_price,
                purchase_from=item.purchase_from,
                notes=item.notes,
            )
            for item in detected
        ],
        compressed_images=compressed_images,
    )


@router.post("/detect-batch", response_model=BatchDetectionResponse)
async def detect_items_batch(
    images: Annotated[list[UploadFile], File(description="Multiple images to analyze in parallel")],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    configs: Annotated[str | None, Form()] = None,
    extract_extended_fields: Annotated[bool, Form()] = True,
) -> BatchDetectionResponse:
    """Analyze multiple images in parallel using LLM vision.

    This endpoint processes all images concurrently, significantly reducing
    total processing time compared to sequential calls to /detect.

    Args:
        images: List of image files to analyze (each treated as separate item(s)).
        ctx: Vision context with auth token, labels, and preferences.
        configs: Optional JSON string with per-image configs.
            Format: [{"single_item": bool, "extra_instructions": str}, ...]
        extract_extended_fields: If True, also extract extended fields for all images.
    """
    logger.info(f"Batch detection for {len(images)} images")

    if not settings.effective_llm_api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Set HBC_LLM_API_KEY or HBC_OPENAI_API_KEY.",
        )

    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    # Parse per-image configs if provided
    image_configs: list[dict] = []
    if configs:
        try:
            image_configs = json.loads(configs)
        except json.JSONDecodeError:
            logger.warning("Invalid configs JSON, using defaults")
            image_configs = []

    logger.debug(f"Loaded {len(ctx.labels)} labels for context (shared across all images)")

    # Read and validate all images
    validated_images = await validate_files_size(images)
    image_data = [(i, img_bytes, mime) for i, (img_bytes, mime) in enumerate(validated_images)]

    # Create detection task for each image
    async def detect_single(
        index: int,
        image_bytes: bytes,
        mime_type: str,
    ) -> BatchDetectionResult:
        """Process a single image and return result."""
        if not image_bytes:
            return BatchDetectionResult(
                image_index=index,
                success=False,
                error="Empty image file",
            )

        # Get config for this image
        config = image_configs[index] if index < len(image_configs) else {}
        single_item = config.get("single_item", False)
        extra_instructions = config.get("extra_instructions")

        try:
            detected = await detect_items_from_bytes(
                image_bytes=image_bytes,
                api_key=settings.effective_llm_api_key,
                mime_type=mime_type,
                model=settings.effective_llm_model,
                labels=ctx.labels,
                single_item=single_item,
                extra_instructions=extra_instructions,
                extract_extended_fields=extract_extended_fields,
                field_preferences=ctx.field_preferences,
                output_language=ctx.output_language,
            )

            # Filter out default label from AI suggestions (frontend will auto-add it)
            return BatchDetectionResult(
                image_index=index,
                success=True,
                items=[
                    DetectedItemResponse(
                        name=item.name,
                        quantity=item.quantity,
                        description=item.description,
                        label_ids=filter_default_label(item.label_ids, ctx.default_label_id),
                        manufacturer=item.manufacturer,
                        model_number=item.model_number,
                        serial_number=item.serial_number,
                        purchase_price=item.purchase_price,
                        purchase_from=item.purchase_from,
                        notes=item.notes,
                    )
                    for item in detected
                ],
            )
        except (ModelNotAllowedError, CapabilityNotSupportedError) as e:
            # Configuration/capability errors - provide clear message
            logger.error(f"Configuration error for image {index}: {e}")
            return BatchDetectionResult(
                image_index=index,
                success=False,
                error=str(e),
            )
        except (JSONRepairError, LLMError) as e:
            # LLM service errors
            logger.error(f"LLM error for image {index}: {e}")
            error_msg = str(e)
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            return BatchDetectionResult(
                image_index=index,
                success=False,
                error=f"LLM error: {error_msg}",
            )
        except Exception as e:
            error_msg = str(e) if str(e) else "Detection failed"
            # Truncate long error messages for the response
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            logger.exception(f"Detection failed for image {index}: {error_msg}")
            return BatchDetectionResult(
                image_index=index,
                success=False,
                error=f"Detection failed: {error_msg}",
            )

    # Process all images in parallel
    logger.info(f"Starting parallel detection for {len(images)} images...")
    detection_tasks = [
        detect_single(index, img_bytes, mime_type)
        for index, img_bytes, mime_type in image_data
    ]
    results = await asyncio.gather(*detection_tasks)

    # Sort by image index to maintain order
    results = sorted(results, key=lambda r: r.image_index)

    # Calculate summary stats
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_items = sum(len(r.items) for r in results)

    logger.info(
        f"Batch detection complete: {successful}/{len(results)} images successful, "
        f"{total_items} total items detected"
    )

    return BatchDetectionResponse(
        results=results,
        total_items=total_items,
        successful_images=successful,
        failed_images=failed,
        message=f"Processed {len(results)} images in parallel",
    )


@router.post("/analyze", response_model=AdvancedItemDetails)
async def analyze_item_advanced(
    images: Annotated[list[UploadFile], File(description="Images to analyze")],
    item_name: Annotated[str, Form()],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    item_description: Annotated[str | None, Form()] = None,
) -> AdvancedItemDetails:
    """Analyze multiple images to extract detailed item information."""
    logger.info(f"Advanced analysis for item: {item_name}")
    logger.debug(f"Description: {item_description}")
    logger.debug(f"Number of images: {len(images) if images else 0}")

    if not settings.effective_llm_api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Set HBC_LLM_API_KEY or HBC_OPENAI_API_KEY.",
        )

    if not images:
        logger.warning("No images provided for analysis")
        raise HTTPException(status_code=400, detail="At least one image is required")

    # Validate and convert images to data URIs
    validated_images = await validate_files_size(images)
    image_data_uris = [
        encode_image_bytes_to_data_uri(img_bytes, mime_type)
        for img_bytes, mime_type in validated_images
    ]

    # Analyze images
    try:
        logger.info(f"Analyzing {len(image_data_uris)} images with LLM...")
        details = await analyze_item_details_from_images(
            image_data_uris=image_data_uris,
            item_name=item_name,
            item_description=item_description,
            api_key=settings.effective_llm_api_key,
            model=settings.effective_llm_model,
            labels=ctx.labels,
            field_preferences=ctx.field_preferences,
            output_language=ctx.output_language,
        )
        logger.info("Analysis complete")
    except (ModelNotAllowedError, CapabilityNotSupportedError, JSONRepairError, LLMError) as e:
        logger.error(f"Analysis failed: {e}")
        raise _llm_error_to_http(e) from e
    except Exception as e:
        logger.exception("Analysis failed unexpectedly")
        raise HTTPException(status_code=500, detail="Analysis failed") from e

    # Filter out default label from AI suggestions (frontend will auto-add it)
    return AdvancedItemDetails(
        name=details.get("name"),
        description=details.get("description"),
        serial_number=details.get("serialNumber"),
        model_number=details.get("modelNumber"),
        manufacturer=details.get("manufacturer"),
        purchase_price=details.get("purchasePrice"),
        notes=details.get("notes"),
        label_ids=filter_default_label(details.get("labelIds"), ctx.default_label_id),
    )


@router.post("/merge", response_model=MergedItemResponse)
async def merge_items(
    request: MergeItemsRequest,
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
) -> MergedItemResponse:
    """Merge multiple items into a single consolidated item using AI."""
    logger.info(f"Merging {len(request.items)} items")

    if not settings.effective_llm_api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Set HBC_LLM_API_KEY or HBC_OPENAI_API_KEY.",
        )

    if len(request.items) < 2:
        raise HTTPException(status_code=400, detail="At least 2 items are required to merge")

    # Convert typed items to dicts for the LLM function
    items_as_dicts = [item.model_dump(exclude_none=True) for item in request.items]

    try:
        logger.info("Calling LLM for item merge...")
        merged = await merge_items_with_openai(
            items=items_as_dicts,
            api_key=settings.effective_llm_api_key,
            model=settings.effective_llm_model,
            labels=ctx.labels,
            field_preferences=ctx.field_preferences,
            output_language=ctx.output_language,
        )
        logger.info(f"Merge complete: {merged.get('name')}")
    except (ModelNotAllowedError, CapabilityNotSupportedError, JSONRepairError, LLMError) as e:
        logger.error(f"Merge failed: {e}")
        raise _llm_error_to_http(e) from e
    except Exception as e:
        logger.exception("Merge failed unexpectedly")
        raise HTTPException(status_code=500, detail="Merge failed") from e

    # Filter out default label from AI suggestions (frontend will auto-add it)
    return MergedItemResponse(
        name=merged.get("name", "Merged Item"),
        quantity=merged.get("quantity", sum(item.quantity for item in request.items)),
        description=merged.get("description"),
        label_ids=filter_default_label(merged.get("labelIds"), ctx.default_label_id),
    )


# Maximum length for correction instructions to prevent abuse
MAX_CORRECTION_INSTRUCTIONS_LENGTH = 2000


@router.post("/correct", response_model=CorrectionResponse)
async def correct_item(
    image: Annotated[UploadFile, File(description="Original image of the item")],
    current_item: Annotated[str, Form(description="JSON string of current item")],
    correction_instructions: Annotated[str, Form(description="User's correction feedback")],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
) -> CorrectionResponse:
    """Correct an item based on user feedback.

    This endpoint allows users to provide feedback about a detected item,
    and the AI will re-analyze with the feedback.
    """
    logger.info("Item correction request received")

    # Validate correction instructions
    if not correction_instructions or not correction_instructions.strip():
        raise HTTPException(status_code=400, detail="Correction instructions are required")

    if len(correction_instructions) > MAX_CORRECTION_INSTRUCTIONS_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Correction instructions too long. "
                f"Maximum {MAX_CORRECTION_INSTRUCTIONS_LENGTH} characters allowed."
            ),
        )

    # Sanitize - strip and truncate for safety
    correction_instructions = correction_instructions.strip()[:MAX_CORRECTION_INSTRUCTIONS_LENGTH]
    preview = correction_instructions[:100]
    logger.debug(f"Correction instructions ({len(correction_instructions)} chars): {preview}...")

    if not settings.effective_llm_api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Set HBC_LLM_API_KEY or HBC_OPENAI_API_KEY.",
        )

    # Parse current item from JSON string
    try:
        current_item_dict = json.loads(current_item)
    except json.JSONDecodeError as e:
        logger.exception("Invalid JSON for current_item")
        raise HTTPException(status_code=400, detail="Invalid current_item JSON") from e

    logger.debug(f"Current item: {current_item_dict}")

    # Read and validate image size
    image_bytes = await validate_file_size(image)
    content_type = image.content_type or "image/jpeg"
    image_data_uri = encode_image_bytes_to_data_uri(image_bytes, content_type)

    logger.debug(f"Loaded {len(ctx.labels)} labels for context")

    # Call the correction function
    try:
        logger.info("Starting LLM item correction...")
        corrected_items = await correct_item_with_openai(
            image_data_uri=image_data_uri,
            current_item=current_item_dict,
            correction_instructions=correction_instructions,
            api_key=settings.effective_llm_api_key,
            model=settings.effective_llm_model,
            labels=ctx.labels,
            field_preferences=ctx.field_preferences,
            output_language=ctx.output_language,
        )
        logger.info(f"Correction resulted in {len(corrected_items)} item(s)")
    except (ModelNotAllowedError, CapabilityNotSupportedError, JSONRepairError, LLMError) as e:
        logger.error(f"Correction failed: {e}")
        raise _llm_error_to_http(e) from e
    except Exception as e:
        logger.exception("Item correction failed unexpectedly")
        raise HTTPException(status_code=500, detail="Correction failed") from e

    # Filter out default label from AI suggestions (frontend will auto-add it)
    return CorrectionResponse(
        items=[
            CorrectedItemResponse(
                name=item.get("name", "Unknown"),
                quantity=item.get("quantity", 1),
                description=item.get("description"),
                label_ids=filter_default_label(item.get("labelIds"), ctx.default_label_id),
                manufacturer=item.get("manufacturer"),
                model_number=item.get("modelNumber") or item.get("model_number"),
                serial_number=item.get("serialNumber") or item.get("serial_number"),
                purchase_price=item.get("purchasePrice") or item.get("purchase_price"),
                purchase_from=item.get("purchaseFrom") or item.get("purchase_from"),
                notes=item.get("notes"),
            )
            for item in corrected_items
        ],
        message=f"Corrected to {len(corrected_items)} item(s)",
    )
