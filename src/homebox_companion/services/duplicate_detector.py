"""Duplicate detection service for preventing duplicate items.

This service checks for potential duplicate items by comparing serial numbers
against existing items in Homebox.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..homebox import HomeboxClient


@dataclass
class ExistingItem:
    """Summary of an existing item in Homebox."""

    id: str
    name: str
    serial_number: str
    location_id: str | None = None
    location_name: str | None = None


@dataclass
class DuplicateMatch:
    """A match between a new item and an existing item."""

    item_index: int
    """Index of the new item in the submitted list."""

    item_name: str
    """Name of the new item."""

    serial_number: str
    """The matching serial number (normalized)."""

    existing_item: ExistingItem
    """The existing item that matches."""


class DuplicateDetector:
    """Detects potential duplicate items by serial number.

    This service helps prevent accidentally adding duplicate items to Homebox
    by checking serial numbers against existing inventory.

    Usage:
        detector = DuplicateDetector(homebox_client)
        matches = await detector.find_duplicates(token, items)
        if matches:
            # Warn user about potential duplicates
    """

    def __init__(self, client: HomeboxClient) -> None:
        """Initialize the duplicate detector.

        Args:
            client: The HomeboxClient instance for API calls.
        """
        self._client = client
        self._serial_index: dict[str, ExistingItem] | None = None

    @staticmethod
    def normalize_serial(serial: str | None) -> str | None:
        """Normalize a serial number for comparison.

        Args:
            serial: The serial number to normalize.

        Returns:
            Uppercase, trimmed serial or None if empty/None.
        """
        if not serial:
            return None
        normalized = serial.strip().upper()
        return normalized if normalized else None

    async def build_serial_index(self, token: str) -> dict[str, ExistingItem]:
        """Fetch all items and build an index by serial number.

        Args:
            token: Bearer token for authentication.

        Returns:
            Dictionary mapping normalized serial numbers to existing items.
        """
        logger.debug("Fetching existing items to build serial number index")

        try:
            items = await self._client.list_items(token)
        except Exception as e:
            logger.warning(f"Failed to fetch items for duplicate check: {e}")
            return {}

        index: dict[str, ExistingItem] = {}
        items_with_serial = 0

        for item in items:
            serial = self.normalize_serial(item.get("serialNumber"))
            if serial:
                items_with_serial += 1
                # Extract location info if available
                location = item.get("location") or {}
                index[serial] = ExistingItem(
                    id=item.get("id", ""),
                    name=item.get("name", "Unknown"),
                    serial_number=serial,
                    location_id=location.get("id"),
                    location_name=location.get("name"),
                )

        logger.info(
            f"Built serial index: {items_with_serial} items with serial numbers "
            f"out of {len(items)} total items"
        )
        self._serial_index = index
        return index

    async def find_duplicates(
        self,
        token: str,
        items: list[dict],
        *,
        rebuild_index: bool = True,
    ) -> list[DuplicateMatch]:
        """Find potential duplicates by checking serial numbers.

        Args:
            token: Bearer token for authentication.
            items: List of item dicts to check (must have 'serial_number' or 'serialNumber').
            rebuild_index: If True, fetch fresh data. If False, use cached index.

        Returns:
            List of DuplicateMatch objects for items with matching serials.
        """
        # Build or refresh the index
        if rebuild_index or self._serial_index is None:
            index = await self.build_serial_index(token)
        else:
            index = self._serial_index

        if not index:
            logger.debug("No existing items with serial numbers, skipping duplicate check")
            return []

        matches: list[DuplicateMatch] = []
        checked_count = 0

        for i, item in enumerate(items):
            # Support both snake_case and camelCase
            serial = item.get("serial_number") or item.get("serialNumber")
            normalized = self.normalize_serial(serial)

            if not normalized:
                continue

            checked_count += 1

            if normalized in index:
                existing = index[normalized]
                item_name = item.get("name", "Unknown")
                matches.append(
                    DuplicateMatch(
                        item_index=i,
                        item_name=item_name,
                        serial_number=normalized,
                        existing_item=existing,
                    )
                )
                logger.warning(
                    f"Potential duplicate found: '{item_name}' has serial '{normalized}' "
                    f"matching existing item '{existing.name}' (ID: {existing.id})"
                )

        logger.info(
            f"Duplicate check complete: {len(matches)} potential duplicates found "
            f"out of {checked_count} items with serial numbers"
        )
        return matches

    def clear_cache(self) -> None:
        """Clear the cached serial number index.

        Call this after creating new items to ensure fresh data on next check.
        """
        self._serial_index = None
        logger.debug("Serial number index cache cleared")
