"""Homebox Service for orchestrating Homebox API operations.

This service encapsulates all Homebox API interactions including
item creation, location management, and label operations.
It provides consistent error handling and logging.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from homebox_vision import AsyncHomeboxClient, AuthenticationError, DetectedItem, settings


class HomeboxService:
    """Service for Homebox API orchestration.

    This class orchestrates Homebox API calls with consistent
    error handling, logging, and retry logic.
    """

    def __init__(
        self,
        client: AsyncHomeboxClient | None = None,
        base_url: str | None = None,
    ):
        """Initialize the Homebox service.

        Args:
            client: Existing AsyncHomeboxClient to use.
            base_url: Base URL for new client. Defaults to HOMEBOX_VISION_API_URL.
        """
        self._client = client
        self._base_url = base_url or settings.api_url
        self._owns_client = client is None

    @property
    def client(self) -> AsyncHomeboxClient:
        """Get or create the Homebox client."""
        if self._client is None:
            self._client = AsyncHomeboxClient(base_url=self._base_url)
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        """Close the client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def login(self, username: str, password: str) -> str:
        """Authenticate with Homebox.

        Args:
            username: User's email address.
            password: User's password.

        Returns:
            Bearer token for subsequent requests.

        Raises:
            AuthenticationError: If login fails.
        """
        logger.info(f"Homebox Service: Login attempt for {username}")

        try:
            token = await self.client.login(username, password)
            logger.info(f"Homebox Service: Login successful for {username}")
            return token
        except Exception as e:
            logger.warning(f"Homebox Service: Login failed for {username} - {e}")
            raise

    async def list_locations(
        self,
        token: str,
        filter_children: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Get all locations.

        Args:
            token: Bearer token.
            filter_children: If True, return only top-level locations.

        Returns:
            List of location dictionaries.
        """
        logger.debug(f"Homebox Service: Listing locations (filter_children={filter_children})")

        try:
            locations = await self.client.list_locations(token, filter_children=filter_children)
            logger.debug(f"Homebox Service: Found {len(locations)} locations")
            return locations
        except AuthenticationError:
            logger.warning("Homebox Service: Token expired or invalid")
            raise
        except Exception as e:
            logger.error(f"Homebox Service: Failed to list locations - {e}")
            raise

    async def get_location(self, token: str, location_id: str) -> dict[str, Any]:
        """Get a specific location with children.

        Args:
            token: Bearer token.
            location_id: ID of the location.

        Returns:
            Location dictionary with children.
        """
        logger.debug(f"Homebox Service: Getting location {location_id}")

        try:
            location = await self.client.get_location(token, location_id)
            logger.debug(f"Homebox Service: Got location '{location.get('name')}'")
            return location
        except AuthenticationError:
            logger.warning("Homebox Service: Token expired or invalid")
            raise
        except Exception as e:
            logger.error(f"Homebox Service: Failed to get location {location_id} - {e}")
            raise

    async def list_labels(self, token: str) -> list[dict[str, Any]]:
        """Get all labels.

        Args:
            token: Bearer token.

        Returns:
            List of label dictionaries.
        """
        logger.debug("Homebox Service: Listing labels")

        try:
            labels = await self.client.list_labels(token)
            logger.debug(f"Homebox Service: Found {len(labels)} labels")
            return labels
        except AuthenticationError:
            logger.warning("Homebox Service: Token expired or invalid")
            raise
        except Exception as e:
            logger.error(f"Homebox Service: Failed to list labels - {e}")
            raise

    async def create_item(
        self,
        token: str,
        item: DetectedItem,
        apply_extended_fields: bool = True,
    ) -> dict[str, Any]:
        """Create an item with optional extended fields.

        Args:
            token: Bearer token.
            item: The item to create.
            apply_extended_fields: If True and item has extended fields,
                perform a follow-up update to apply them.

        Returns:
            The created (and optionally updated) item.
        """
        logger.info(f"Homebox Service: Creating item '{item.name}'")

        try:
            result = await self.client.create_item(token, item)
            item_id = result.get("id")
            logger.info(f"Homebox Service: Created item (id: {item_id})")

            # Apply extended fields if present
            if apply_extended_fields and item_id and item.has_extended_fields():
                extended_payload = item.get_extended_fields_payload()
                if extended_payload:
                    logger.debug(f"Homebox Service: Applying extended fields to {item_id}")
                    full_item = await self.client.get_item(token, item_id)
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
                    result = await self.client.update_item(token, item_id, update_data)
                    logger.info("Homebox Service: Applied extended fields")

            return result
        except AuthenticationError:
            logger.warning("Homebox Service: Token expired or invalid")
            raise
        except Exception as e:
            logger.error(f"Homebox Service: Failed to create item '{item.name}' - {e}")
            raise

    async def create_items_batch(
        self,
        token: str,
        items: list[DetectedItem],
        location_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Create multiple items in batch.

        Args:
            token: Bearer token.
            items: List of items to create.
            location_id: Default location ID for items without one.

        Returns:
            Tuple of (created items, error messages).
        """
        logger.info(f"Homebox Service: Creating {len(items)} items in batch")

        created: list[dict[str, Any]] = []
        errors: list[str] = []

        for item in items:
            # Apply default location if item doesn't have one
            if location_id and not item.location_id:
                item.location_id = location_id

            try:
                result = await self.create_item(token, item)
                created.append(result)
            except Exception as e:
                error_msg = f"Failed to create '{item.name}': {e}"
                logger.error(f"Homebox Service: {error_msg}")
                errors.append(error_msg)

        logger.info(
            f"Homebox Service: Batch complete - {len(created)} created, {len(errors)} failed"
        )
        return created, errors

    async def upload_attachment(
        self,
        token: str,
        item_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        attachment_type: str = "photo",
    ) -> dict[str, Any]:
        """Upload an attachment to an item.

        Args:
            token: Bearer token.
            item_id: ID of the item.
            file_bytes: File content.
            filename: Name for the file.
            mime_type: MIME type of the file.
            attachment_type: Type of attachment (default: "photo").

        Returns:
            Attachment response.
        """
        logger.info(f"Homebox Service: Uploading attachment to item {item_id}")

        try:
            result = await self.client.upload_attachment(
                token=token,
                item_id=item_id,
                file_bytes=file_bytes,
                filename=filename,
                mime_type=mime_type,
                attachment_type=attachment_type,
            )
            logger.info(f"Homebox Service: Uploaded attachment '{filename}'")
            return result
        except AuthenticationError:
            logger.warning("Homebox Service: Token expired or invalid")
            raise
        except Exception as e:
            logger.error(f"Homebox Service: Failed to upload attachment - {e}")
            raise
