"""Vision tool API routes."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

from homebox_companion import (
    CapabilityNotSupportedError,
    JSONRepairError,
    LLMServiceError,
    analyze_item_details_from_images,
    detect_items_from_bytes,
    encode_compressed_image_to_base64,
    encode_image_bytes_to_data_uri,
    grouped_detect_items,
    settings,
)
from homebox_companion import (
    correct_item as llm_correct_item,
)

from ...dependencies import (
    LLMConfig,
    VisionContext,
    get_configured_llm_with_fallback,
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
    GroupedDetectionResponse,
    TokenUsageResponse,
)

router = APIRouter()

# Limit concurrent CPU-intensive compression to available cores.
# This prevents 100+ parallel requests from overwhelming the CPU.
# We track both the semaphore and the event loop it was created for,
# so we can recreate it if the loop changes (e.g., during tests or reloads).
_COMPRESSION_SEMAPHORE: asyncio.Semaphore | None = None
_COMPRESSION_SEMAPHORE_LOOP: asyncio.AbstractEventLoop | None = None


def _get_compression_semaphore() -> asyncio.Semaphore:
    """Get or create the compression semaphore for the current event loop.

    The semaphore is bound to the event loop it was created on.
    If the loop changes (tests, reloads), we create a new semaphore.

    Note: This function is safe from race conditions in async code because:
    - There's no `await` between the check and the assignment
    - Asyncio is cooperative, so this runs atomically within a single event loop
    """
    global _COMPRESSION_SEMAPHORE, _COMPRESSION_SEMAPHORE_LOOP

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - this shouldn't happen in normal request handling
        # but can occur in tests. Create semaphore anyway; it will be
        # recreated when a proper loop is running.
        current_loop = None

    # Recreate semaphore if loop changed or doesn't exist
    if (
        _COMPRESSION_SEMAPHORE is None
        or _COMPRESSION_SEMAPHORE_LOOP is None
        or (current_loop is not None and _COMPRESSION_SEMAPHORE_LOOP is not current_loop)
    ):
        _COMPRESSION_SEMAPHORE = asyncio.Semaphore(os.cpu_count() or 4)
        _COMPRESSION_SEMAPHORE_LOOP = current_loop

    return _COMPRESSION_SEMAPHORE


def convert_usage_to_response(usage) -> TokenUsageResponse | None:
    """Convert internal TokenUsage to response schema.

    Args:
        usage: TokenUsage object from detection result.

    Returns:
        TokenUsageResponse schema or None if no usage data.
    """
    if usage is None:
        return None
    return TokenUsageResponse(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        provider=usage.provider,
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


def get_llm_model_for_litellm(llm_config: LLMConfig) -> str:
    """Get the model name formatted for LiteLLM.

    For Ollama and Anthropic providers, we need to prefix the model name
    so LiteLLM routes to the correct provider.

    Args:
        llm_config: The LLM configuration.

    Returns:
        Model name formatted for LiteLLM.
    """
    if llm_config.provider == "ollama":
        # Ollama models need prefix for LiteLLM routing
        if not llm_config.model.startswith("ollama/"):
            return f"ollama/{llm_config.model}"
    elif llm_config.provider == "anthropic":
        # Anthropic models need prefix for LiteLLM
        if not llm_config.model.startswith("anthropic/"):
            return f"anthropic/{llm_config.model}"
    elif llm_config.provider == "openai":
        # OpenAI models work as-is with LiteLLM
        pass
    # For litellm provider, use model as-is (user controls the full model string)
    return llm_config.model


async def run_with_fallback(
    primary_config: LLMConfig,
    fallback_config: LLMConfig | None,
    operation_name: str,
    async_fn,
    *args,
    **kwargs,
):
    """Run an async function with fallback provider support.

    If the primary provider fails and a fallback is configured,
    retry with the fallback provider.

    Args:
        primary_config: Primary LLM configuration.
        fallback_config: Fallback LLM configuration (or None).
        operation_name: Name of the operation for logging.
        async_fn: Async function to call.
        *args, **kwargs: Arguments to pass to the function.
            The function should accept 'api_key', 'model', and 'api_base' kwargs.

    Returns:
        Result from the async function.

    Raises:
        The original exception if fallback is not available or also fails.
    """
    try:
        # Try primary provider
        return await async_fn(
            *args,
            api_key=primary_config.api_key,
            model=get_llm_model_for_litellm(primary_config),
            api_base=primary_config.api_base,
            **kwargs,
        )
    except Exception as primary_error:
        # Log primary failure
        error_msg = str(primary_error)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        logger.error(
            f"[FALLBACK] Primary provider '{primary_config.provider}' failed for {operation_name}: "
            f"{type(primary_error).__name__}: {error_msg}"
        )

        # Check if fallback is available
        if fallback_config is None:
            logger.info(f"[FALLBACK] No fallback configured, re-raising error")
            raise

        # Try fallback provider
        logger.info(
            f"[FALLBACK] Attempting fallback to '{fallback_config.provider}' "
            f"(model: {fallback_config.model})"
        )
        try:
            result = await async_fn(
                *args,
                api_key=fallback_config.api_key,
                model=get_llm_model_for_litellm(fallback_config),
                api_base=fallback_config.api_base,
                **kwargs,
            )
            logger.info(f"[FALLBACK] Fallback to '{fallback_config.provider}' succeeded")
            return result
        except Exception as fallback_error:
            fallback_msg = str(fallback_error)
            if len(fallback_msg) > 200:
                fallback_msg = fallback_msg[:200] + "..."
            logger.error(
                f"[FALLBACK] Fallback provider '{fallback_config.provider}' also failed: "
                f"{type(fallback_error).__name__}: {fallback_msg}"
            )
            # Re-raise the original error (primary failure is more relevant)
            raise primary_error from fallback_error


@router.post("/detect", response_model=DetectionResponse)
async def detect_items(
    image: Annotated[UploadFile, File(description="Primary image file to analyze")],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    llm_configs: Annotated[tuple[LLMConfig, LLMConfig | None], Depends(get_configured_llm_with_fallback)],
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
        llm_configs: Tuple of (primary_config, fallback_config) for LLM.
        single_item: If True, treat everything as a single item.
        extra_instructions: Optional user hint about what's in the image.
        extract_extended_fields: If True, also extract extended fields.
        additional_images: Optional additional images for the same item(s).
    """
    llm_config, fallback_config = llm_configs
    additional_count = len(additional_images) if additional_images else 0
    logger.info(f"Detecting items from image: {image.filename} (+ {additional_count} additional)")
    logger.info(f"Using provider: {llm_config.provider}, model: {llm_config.model}")
    if fallback_config:
        logger.info(f"Fallback enabled: {fallback_config.provider}, model: {fallback_config.model}")
    logger.info(f"Single item mode: {single_item}, Extra instructions: {extra_instructions}")
    logger.info(f"Extract extended fields: {extract_extended_fields}")

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
        """Compress all images (primary + additional) for Homebox upload in parallel."""
        all_images_to_compress = [(image_bytes, content_type)] + additional_image_data

        async def compress_one(img_bytes: bytes, _mime: str) -> CompressedImage:
            """Compress a single image with concurrency limiting."""
            # Limit concurrent compressions to prevent CPU overload
            async with _get_compression_semaphore():
                base64_data, mime = await asyncio.to_thread(
                    encode_compressed_image_to_base64, img_bytes, max_dimension, jpeg_quality
                )
                return CompressedImage(data=base64_data, mime_type=mime)

        # Compress all images in parallel
        return await asyncio.gather(
            *[compress_one(img_bytes, mime) for img_bytes, mime in all_images_to_compress]
        )

    # Detect items
    logger.info("Starting LLM vision detection and image compression...")

    # Detection function with fallback support
    async def run_detection():
        return await run_with_fallback(
            primary_config=llm_config,
            fallback_config=fallback_config,
            operation_name="detect_items",
            async_fn=detect_items_from_bytes,
            image_bytes=image_bytes,
            mime_type=content_type,
            labels=ctx.labels,
            single_item=single_item,
            extra_instructions=extra_instructions,
            extract_extended_fields=extract_extended_fields,
            additional_images=additional_image_data,
            field_preferences=ctx.field_preferences,
            output_language=ctx.output_language,
        )

    # Run detection (with fallback) and compression in parallel
    detection_task = run_detection()
    compression_task = compress_all_images()

    detection_result, compressed_images = await asyncio.gather(detection_task, compression_task)

    logger.info(f"Detected {len(detection_result.items)} items, compressed {len(compressed_images)} images")

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
            for item in detection_result.items
        ],
        compressed_images=compressed_images,
        usage=convert_usage_to_response(detection_result.usage),
    )


@router.post("/detect-batch", response_model=BatchDetectionResponse)
async def detect_items_batch(
    images: Annotated[list[UploadFile], File(description="Multiple images to analyze in parallel")],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    llm_configs: Annotated[tuple[LLMConfig, LLMConfig | None], Depends(get_configured_llm_with_fallback)],
    configs: Annotated[str | None, Form()] = None,
    extract_extended_fields: Annotated[bool, Form()] = True,
) -> BatchDetectionResponse:
    """Analyze multiple images in parallel using LLM vision.

    This endpoint processes all images concurrently, significantly reducing
    total processing time compared to sequential calls to /detect.

    Args:
        images: List of image files to analyze (each treated as separate item(s)).
        ctx: Vision context with auth token, labels, and preferences.
        llm_configs: Tuple of (primary_config, fallback_config) for LLM.
        configs: Optional JSON string with per-image configs.
            Format: [{"single_item": bool, "extra_instructions": str}, ...]
        extract_extended_fields: If True, also extract extended fields for all images.
    """
    llm_config, fallback_config = llm_configs
    logger.info(f"Batch detection for {len(images)} images")
    if fallback_config:
        logger.info(f"Fallback enabled: {fallback_config.provider}, model: {fallback_config.model}")

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
        """Process a single image and return result (with fallback support)."""
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
            # Use fallback wrapper for detection
            detection_result = await run_with_fallback(
                primary_config=llm_config,
                fallback_config=fallback_config,
                operation_name=f"detect_items_batch[{index}]",
                async_fn=detect_items_from_bytes,
                image_bytes=image_bytes,
                mime_type=mime_type,
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
                    for item in detection_result.items
                ],
                usage=convert_usage_to_response(detection_result.usage),
            )
        except CapabilityNotSupportedError as e:
            # Configuration/capability errors - provide clear message
            logger.error(f"Configuration error for image {index}: {e}")
            return BatchDetectionResult(
                image_index=index,
                success=False,
                error=str(e),
            )
        except (JSONRepairError, LLMServiceError) as e:
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
        detect_single(index, img_bytes, mime_type) for index, img_bytes, mime_type in image_data
    ]
    results = await asyncio.gather(*detection_tasks)

    # Sort by image index to maintain order
    results = sorted(results, key=lambda r: r.image_index)

    # Calculate summary stats
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    total_items = sum(len(r.items) for r in results)

    # Aggregate token usage across all successful results
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_total_tokens = 0
    provider = "unknown"
    for r in results:
        if r.usage:
            total_prompt_tokens += r.usage.prompt_tokens
            total_completion_tokens += r.usage.completion_tokens
            total_total_tokens += r.usage.total_tokens
            provider = r.usage.provider  # Use the last provider

    # Only include total_usage if any tokens were counted
    total_usage = None
    if total_total_tokens > 0:
        total_usage = TokenUsageResponse(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_total_tokens,
            provider=provider,
        )

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
        total_usage=total_usage,
    )


@router.post("/detect-grouped", response_model=GroupedDetectionResponse)
async def detect_items_grouped(
    images: Annotated[list[UploadFile], File(description="Multiple images to analyze together")],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    llm_configs: Annotated[tuple[LLMConfig, LLMConfig | None], Depends(get_configured_llm_with_fallback)],
    extra_instructions: Annotated[str | None, Form()] = None,
    extract_extended_fields: Annotated[bool, Form()] = True,
) -> GroupedDetectionResponse:
    """Analyze multiple images together with automatic grouping.

    Unlike /detect-batch which processes images independently, this endpoint
    sends ALL images to the AI in a single request and asks it to:
    1. Identify unique items across all images
    2. Group images that show the same physical item

    Use this when:
    - Multiple images may show the same item from different angles
    - You want the AI to automatically determine which images go together
    - You don't know ahead of time how images should be grouped

    Each returned item includes `image_indices` indicating which images show it.

    Args:
        images: List of image files to analyze together.
        ctx: Vision context with auth token, labels, and preferences.
        llm_configs: Tuple of (primary_config, fallback_config) for LLM.
        extra_instructions: Optional user hint about image contents.
        extract_extended_fields: If True, also extract extended fields.
    """
    llm_config, fallback_config = llm_configs
    logger.info(f"Grouped detection for {len(images)} images")
    if fallback_config:
        logger.info(f"Fallback enabled: {fallback_config.provider}, model: {fallback_config.model}")

    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")

    if len(images) < 2:
        raise HTTPException(
            status_code=400,
            detail="Grouped detection requires at least 2 images. Use /detect for single images.",
        )

    logger.debug(f"Loaded {len(ctx.labels)} labels for context")

    # Read and validate all images
    validated_images = await validate_files_size(images)

    # Convert to data URIs
    image_data_uris = [
        encode_image_bytes_to_data_uri(img_bytes, mime_type)
        for img_bytes, mime_type in validated_images
    ]

    try:
        # Run grouped detection with fallback support
        logger.info(f"Starting grouped detection with {len(image_data_uris)} images...")
        detection_result = await run_with_fallback(
            primary_config=llm_config,
            fallback_config=fallback_config,
            operation_name="grouped_detect_items",
            async_fn=grouped_detect_items,
            image_data_uris=image_data_uris,
            labels=ctx.labels,
            extract_extended_fields=extract_extended_fields,
            extra_instructions=extra_instructions,
            field_preferences=ctx.field_preferences,
            output_language=ctx.output_language,
        )

        logger.info(f"Grouped detection found {len(detection_result.items)} unique items")

        # Filter out default label from AI suggestions
        return GroupedDetectionResponse(
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
                    image_indices=item.image_indices,
                )
                for item in detection_result.items
            ],
            total_images=len(images),
            message=f"Found {len(detection_result.items)} unique items in {len(images)} images",
            usage=convert_usage_to_response(detection_result.usage),
        )
    except CapabilityNotSupportedError as e:
        logger.error(f"Configuration error for grouped detection: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (JSONRepairError, LLMServiceError) as e:
        logger.error(f"LLM error for grouped detection: {e}")
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        raise HTTPException(status_code=500, detail=f"LLM error: {error_msg}") from e


@router.post("/analyze", response_model=AdvancedItemDetails)
async def analyze_item_advanced(
    images: Annotated[list[UploadFile], File(description="Images to analyze")],
    item_name: Annotated[str, Form()],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    llm_configs: Annotated[tuple[LLMConfig, LLMConfig | None], Depends(get_configured_llm_with_fallback)],
    item_description: Annotated[str | None, Form()] = None,
) -> AdvancedItemDetails:
    """Analyze multiple images to extract detailed item information."""
    llm_config, fallback_config = llm_configs
    logger.info(f"Advanced analysis for item: {item_name}")
    if fallback_config:
        logger.info(f"Fallback enabled: {fallback_config.provider}, model: {fallback_config.model}")
    logger.debug(f"Description: {item_description}")
    logger.debug(f"Number of images: {len(images) if images else 0}")

    if not images:
        logger.warning("No images provided for analysis")
        raise HTTPException(status_code=400, detail="At least one image is required")

    # Validate and convert images to data URIs
    validated_images = await validate_files_size(images)
    image_data_uris = [
        encode_image_bytes_to_data_uri(img_bytes, mime_type)
        for img_bytes, mime_type in validated_images
    ]

    # Analyze images with fallback support
    logger.info(f"Analyzing {len(image_data_uris)} images with LLM (provider: {llm_config.provider})...")
    details = await run_with_fallback(
        primary_config=llm_config,
        fallback_config=fallback_config,
        operation_name="analyze_item_details",
        async_fn=analyze_item_details_from_images,
        image_data_uris=image_data_uris,
        item_name=item_name,
        item_description=item_description,
        labels=ctx.labels,
        field_preferences=ctx.field_preferences,
        output_language=ctx.output_language,
    )
    logger.info("Analysis complete")

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


# Maximum length for correction instructions to prevent abuse
MAX_CORRECTION_INSTRUCTIONS_LENGTH = 2000


@router.post("/correct", response_model=CorrectionResponse)
async def correct_item(
    image: Annotated[UploadFile, File(description="Original image of the item")],
    current_item: Annotated[str, Form(description="JSON string of current item")],
    correction_instructions: Annotated[str, Form(description="User's correction feedback")],
    ctx: Annotated[VisionContext, Depends(get_vision_context)],
    llm_configs: Annotated[tuple[LLMConfig, LLMConfig | None], Depends(get_configured_llm_with_fallback)],
) -> CorrectionResponse:
    """Correct an item based on user feedback.

    This endpoint allows users to provide feedback about a detected item,
    and the AI will re-analyze with the feedback.
    """
    llm_config, fallback_config = llm_configs
    logger.info("Item correction request received")
    if fallback_config:
        logger.info(f"Fallback enabled: {fallback_config.provider}, model: {fallback_config.model}")

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

    # Call the correction function with fallback support
    logger.info(f"Starting LLM item correction (provider: {llm_config.provider})...")
    corrected_items = await run_with_fallback(
        primary_config=llm_config,
        fallback_config=fallback_config,
        operation_name="correct_item",
        async_fn=llm_correct_item,
        image_data_uri=image_data_uri,
        current_item=current_item_dict,
        correction_instructions=correction_instructions,
        labels=ctx.labels,
        field_preferences=ctx.field_preferences,
        output_language=ctx.output_language,
    )
    logger.info(f"Correction resulted in {len(corrected_items)} item(s)")

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
