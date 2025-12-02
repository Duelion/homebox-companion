"""AI Service for orchestrating OpenAI vision operations.

This service encapsulates all AI-related operations including item detection,
analysis, merging, and correction. It provides consistent error handling
and logging across all AI operations.
"""

from __future__ import annotations

from typing import Any

from fastapi import UploadFile
from loguru import logger

from homebox_vision import (
    DetectedItem,
    analyze_item_details_from_images,
    correct_item_with_openai,
    detect_items_from_bytes,
    discriminatory_detect_items,
    encode_image_bytes_to_data_uri,
    merge_items_with_openai,
    settings,
)


class AIService:
    """Service for AI-powered item detection and analysis.

    This class orchestrates OpenAI vision API calls for various
    item-related operations in the Homebox Vision app.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialize the AI service.

        Args:
            api_key: OpenAI API key. Defaults to HOMEBOX_VISION_OPENAI_API_KEY.
            model: OpenAI model name. Defaults to HOMEBOX_VISION_OPENAI_MODEL.
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model

    async def detect_items(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        labels: list[dict[str, str]] | None = None,
        single_item: bool = False,
        extra_instructions: str | None = None,
        extract_extended_fields: bool = True,
        additional_images: list[tuple[bytes, str]] | None = None,
    ) -> list[DetectedItem]:
        """Detect items in an image using AI vision.

        Args:
            image_bytes: Raw image data.
            mime_type: MIME type of the image.
            labels: Available Homebox labels for context.
            single_item: If True, treat everything as a single item.
            extra_instructions: User-provided hint about image contents.
            extract_extended_fields: If True, extract manufacturer, model, etc.
            additional_images: Additional images of the same item(s).

        Returns:
            List of detected items.

        Raises:
            Exception: If detection fails.
        """
        logger.info(f"AI Service: Starting detection (single_item={single_item})")

        try:
            items = await detect_items_from_bytes(
                image_bytes=image_bytes,
                api_key=self.api_key,
                mime_type=mime_type,
                model=self.model,
                labels=labels,
                single_item=single_item,
                extra_instructions=extra_instructions,
                extract_extended_fields=extract_extended_fields,
                additional_images=additional_images,
            )
            logger.info(f"AI Service: Detected {len(items)} items")
            return items
        except Exception as e:
            logger.error(f"AI Service: Detection failed - {e}")
            raise

    async def analyze_item_details(
        self,
        images: list[UploadFile],
        item_name: str,
        item_description: str | None = None,
        labels: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Analyze multiple images for detailed item information.

        Args:
            images: List of image files to analyze.
            item_name: The name of the item being analyzed.
            item_description: Optional initial description.
            labels: Available Homebox labels for context.

        Returns:
            Dictionary with extracted item details.

        Raises:
            Exception: If analysis fails.
        """
        logger.info(f"AI Service: Analyzing {len(images)} images for '{item_name}'")

        # Convert images to data URIs
        image_data_uris = []
        for img in images:
            img_bytes = await img.read()
            if img_bytes:
                mime_type = img.content_type or "image/jpeg"
                data_uri = encode_image_bytes_to_data_uri(img_bytes, mime_type)
                image_data_uris.append(data_uri)

        if not image_data_uris:
            raise ValueError("No valid images provided for analysis")

        try:
            details = await analyze_item_details_from_images(
                image_data_uris=image_data_uris,
                item_name=item_name,
                item_description=item_description,
                api_key=self.api_key,
                model=self.model,
                labels=labels,
            )
            logger.info(f"AI Service: Analysis complete, fields: {list(details.keys())}")
            return details
        except Exception as e:
            logger.error(f"AI Service: Analysis failed - {e}")
            raise

    async def merge_items(
        self,
        items: list[dict[str, Any]],
        labels: list[dict[str, str]] | None = None,
        image_data_uris: list[str] | None = None,
    ) -> dict[str, Any]:
        """Merge multiple items into a consolidated item.

        Args:
            items: List of items to merge.
            labels: Available Homebox labels for context.
            image_data_uris: Optional images for additional context.

        Returns:
            Merged item data.

        Raises:
            Exception: If merge fails.
        """
        logger.info(f"AI Service: Merging {len(items)} items")

        try:
            merged = await merge_items_with_openai(
                items=items,
                api_key=self.api_key,
                model=self.model,
                labels=labels,
                image_data_uris=image_data_uris,
            )
            logger.info(f"AI Service: Merged into '{merged.get('name')}'")
            return merged
        except Exception as e:
            logger.error(f"AI Service: Merge failed - {e}")
            raise

    async def correct_item(
        self,
        image_data_uri: str,
        current_item: dict[str, Any],
        correction_instructions: str,
        labels: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Correct an item based on user feedback.

        Args:
            image_data_uri: Data URI of the image.
            current_item: Current item data.
            correction_instructions: User's correction text.
            labels: Available Homebox labels for context.

        Returns:
            List of corrected items (may be multiple if split).

        Raises:
            Exception: If correction fails.
        """
        logger.info(f"AI Service: Correcting '{current_item.get('name')}'")
        logger.debug(f"Instructions: {correction_instructions}")

        try:
            corrected = await correct_item_with_openai(
                image_data_uri=image_data_uri,
                current_item=current_item,
                correction_instructions=correction_instructions,
                api_key=self.api_key,
                model=self.model,
                labels=labels,
            )
            logger.info(f"AI Service: Correction resulted in {len(corrected)} item(s)")
            return corrected
        except Exception as e:
            logger.error(f"AI Service: Correction failed - {e}")
            raise

    async def discriminatory_detect(
        self,
        image_data_uris: list[str],
        previous_merged_item: dict[str, Any] | None = None,
        labels: list[dict[str, str]] | None = None,
        extract_extended_fields: bool = True,
    ) -> list[DetectedItem]:
        """Re-detect items with more discriminatory instructions.

        Used when unmerging items to get more specific detection.

        Args:
            image_data_uris: List of image data URIs.
            previous_merged_item: The previously merged item for context.
            labels: Available Homebox labels for context.
            extract_extended_fields: If True, extract extended fields.

        Returns:
            List of more specifically detected items.

        Raises:
            Exception: If detection fails.
        """
        logger.info(f"AI Service: Discriminatory detection on {len(image_data_uris)} images")

        try:
            items = await discriminatory_detect_items(
                image_data_uris=image_data_uris,
                previous_merged_item=previous_merged_item,
                api_key=self.api_key,
                model=self.model,
                labels=labels,
                extract_extended_fields=extract_extended_fields,
            )
            logger.info(f"AI Service: Discriminatory detection found {len(items)} items")
            return items
        except Exception as e:
            logger.error(f"AI Service: Discriminatory detection failed - {e}")
            raise
