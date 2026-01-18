"""Duplicate Detection Service.

Checks for potential duplicate items by querying Homebox directly.
Uses exact serial number matching with case-insensitive normalization.
"""

from dataclasses import dataclass

from loguru import logger

from homebox_companion import HomeboxClient


@dataclass
class DuplicateMatch:
    """An existing item that matches the new item's serial number."""

    item_id: str
    item_name: str
    serial_number: str
    location_name: str | None = None


class DuplicateChecker:
    """Check for duplicate items by querying Homebox. No persistent state.

    This service performs exact serial number matching by:
    1. Searching Homebox for items matching the serial number query
    2. Fetching full details for each candidate (since serial isn't in search results)
    3. Comparing normalized serial numbers for exact match

    Usage:
        checker = DuplicateChecker(client)
        match = await checker.check_serial_number(token, "ABC123")
        if match:
            print(f"Duplicate found: {match.item_name}")
    """

    # Maximum candidates to check (API doesn't expose serial in search results)
    MAX_CANDIDATES = 10

    def __init__(self, client: HomeboxClient) -> None:
        """Initialize the duplicate checker.

        Args:
            client: HomeboxClient for API queries.
        """
        self.client = client

    async def check_serial_number(
        self,
        token: str,
        serial: str,
    ) -> DuplicateMatch | None:
        """Check if an item with this serial number already exists.

        Args:
            token: Bearer token for Homebox API.
            serial: Serial number to check (will be normalized).

        Returns:
            DuplicateMatch if an existing item has this serial, else None.
        """
        # Skip empty/whitespace-only serials
        if not serial or not serial.strip():
            return None

        normalized = serial.strip().upper()
        logger.debug(f"Checking for duplicate serial: {normalized}")

        # Search Homebox - the query param searches across multiple fields
        try:
            results = await self.client.list_items(token, query=normalized)
        except Exception as e:
            logger.warning(f"Failed to search for duplicates: {e}")
            return None

        items = results.get("items", [])
        logger.debug(f"Found {len(items)} candidate items for serial check")

        # Check each candidate for exact serial match
        # Limit to MAX_CANDIDATES to avoid excessive API calls
        for item_summary in items[: self.MAX_CANDIDATES]:
            try:
                full_item = await self.client.get_item(token, item_summary["id"])
                item_serial = (full_item.get("serialNumber") or "").strip().upper()

                if item_serial == normalized:
                    location = full_item.get("location", {})
                    match = DuplicateMatch(
                        item_id=full_item["id"],
                        item_name=full_item.get("name", "Unknown"),
                        serial_number=full_item.get("serialNumber", ""),
                        location_name=location.get("name") if location else None,
                    )
                    logger.info(f"Duplicate found: '{match.item_name}' (ID: {match.item_id})")
                    return match
            except Exception as e:
                logger.warning(f"Failed to fetch item {item_summary.get('id', '?')}: {e}")
                continue

        logger.debug(f"No duplicate found for serial: {normalized}")
        return None
