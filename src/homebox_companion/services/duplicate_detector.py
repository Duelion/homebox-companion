"""Duplicate detection service for preventing duplicate items.

This service checks for potential duplicate items by comparing serial numbers
against existing items in Homebox.

Features:
- Persistent index storage (survives restarts)
- Differential updates using asset IDs (only fetch new items)
- Manual rebuild capability
- Incremental updates when items are created

Note: The Homebox API's /items list endpoint returns ItemSummary which does NOT
include serialNumber. To get serial numbers, we must fetch individual item details
via /items/{id}. This service fetches details in parallel batches for efficiency.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..core.config import settings

if TYPE_CHECKING:
    from ..homebox import HomeboxClient


# Default path for persisted index
INDEX_FILE = Path(settings.data_dir) / "duplicate_index.json"


@dataclass
class ExistingItem:
    """Summary of an existing item in Homebox."""

    id: str
    name: str
    serial_number: str
    asset_id: int = 0
    location_id: str | None = None
    location_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExistingItem:
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Unknown"),
            serial_number=data.get("serial_number", ""),
            asset_id=data.get("asset_id", 0),
            location_id=data.get("location_id"),
            location_name=data.get("location_name"),
        )


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


@dataclass
class IndexStatus:
    """Status information about the duplicate index."""

    last_build_time: str | None
    """ISO timestamp of last full build."""

    last_update_time: str | None
    """ISO timestamp of last update (full or differential)."""

    total_items_indexed: int
    """Total number of items in Homebox (with or without serial)."""

    items_with_serials: int
    """Number of items with serial numbers in index."""

    highest_asset_id: int
    """Highest asset ID seen (for differential updates)."""

    is_loaded: bool
    """Whether the index is currently loaded in memory."""


class DuplicateDetector:
    """Detects potential duplicate items by serial number.

    This service helps prevent accidentally adding duplicate items to Homebox
    by checking serial numbers against existing inventory.

    Features:
    - Builds index on first use or startup
    - Persists index to disk for fast restarts
    - Differential updates using asset IDs
    - Manual rebuild and incremental update support

    Usage:
        detector = DuplicateDetector(homebox_client)

        # Load persisted index (fast) then update with new items
        await detector.load_or_build(token)

        # Check for duplicates
        matches = await detector.find_duplicates(token, items)

        # After creating items, update index incrementally
        detector.add_item_to_index(created_item)

        # Manual full rebuild
        await detector.rebuild_index(token)
    """

    def __init__(
        self,
        client: HomeboxClient,
        index_path: Path | None = None,
    ) -> None:
        """Initialize the duplicate detector.

        Args:
            client: The HomeboxClient instance for API calls.
            index_path: Path to store persistent index. Defaults to config dir.
        """
        self._client = client
        self._index_path = index_path or INDEX_FILE

        # In-memory index state
        self._serial_index: dict[str, ExistingItem] = {}
        self._known_item_ids: set[str] = set()
        self._highest_asset_id: int = 0
        self._total_items: int = 0
        self._last_build_time: datetime | None = None
        self._last_update_time: datetime | None = None
        self._is_loaded: bool = False

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

    @staticmethod
    def parse_asset_id(asset_id: str | int | None) -> int:
        """Parse asset ID to integer for comparison.

        Homebox asset IDs can be:
        - Integers (e.g., 4)
        - Formatted strings (e.g., "000-004")
        - None or empty

        Args:
            asset_id: The asset ID from Homebox API.

        Returns:
            Integer value of the asset ID, or 0 if unparseable.
        """
        if asset_id is None:
            return 0
        if isinstance(asset_id, int):
            return asset_id
        if isinstance(asset_id, str):
            # Try to extract numeric part from formatted string like "000-004"
            # Remove common separators and leading zeros
            cleaned = asset_id.replace("-", "").replace("_", "").lstrip("0")
            if cleaned.isdigit():
                return int(cleaned)
            # If still not numeric, try to find any digits
            digits = "".join(c for c in asset_id if c.isdigit())
            if digits:
                return int(digits.lstrip("0") or "0")
        return 0

    def get_status(self) -> IndexStatus:
        """Get current index status."""
        return IndexStatus(
            last_build_time=self._last_build_time.isoformat() if self._last_build_time else None,
            last_update_time=self._last_update_time.isoformat() if self._last_update_time else None,
            total_items_indexed=self._total_items,
            items_with_serials=len(self._serial_index),
            highest_asset_id=self._highest_asset_id,
            is_loaded=self._is_loaded,
        )

    def _save_to_disk(self) -> None:
        """Persist index to disk."""
        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": 1,
                "last_build_time": self._last_build_time.isoformat() if self._last_build_time else None,
                "last_update_time": self._last_update_time.isoformat() if self._last_update_time else None,
                "highest_asset_id": self._highest_asset_id,
                "total_items": self._total_items,
                "known_item_ids": list(self._known_item_ids),
                "serial_index": {
                    serial: item.to_dict()
                    for serial, item in self._serial_index.items()
                },
            }

            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved duplicate index to {self._index_path}")
        except Exception as e:
            logger.warning(f"Failed to save duplicate index: {e}")

    def _load_from_disk(self) -> bool:
        """Load index from disk.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if not self._index_path.exists():
            logger.debug("No persisted duplicate index found")
            return False

        try:
            with open(self._index_path, encoding="utf-8") as f:
                data = json.load(f)

            # Check version compatibility
            if data.get("version", 0) != 1:
                logger.warning("Duplicate index version mismatch, will rebuild")
                return False

            # Restore state
            self._last_build_time = (
                datetime.fromisoformat(data["last_build_time"])
                if data.get("last_build_time")
                else None
            )
            self._last_update_time = (
                datetime.fromisoformat(data["last_update_time"])
                if data.get("last_update_time")
                else None
            )
            self._highest_asset_id = data.get("highest_asset_id", 0)
            self._total_items = data.get("total_items", 0)
            self._known_item_ids = set(data.get("known_item_ids", []))

            # Restore serial index
            self._serial_index = {
                serial: ExistingItem.from_dict(item_data)
                for serial, item_data in data.get("serial_index", {}).items()
            }

            self._is_loaded = True
            logger.info(
                f"Loaded duplicate index from disk: {len(self._serial_index)} serials, "
                f"highest asset ID: {self._highest_asset_id}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to load duplicate index from disk: {e}")
            return False

    async def load_or_build(
        self,
        token: str,
        *,
        max_concurrent: int = 10,
    ) -> None:
        """Load persisted index and update with any new items.

        This is the recommended way to initialize the detector:
        1. Load persisted index from disk (fast)
        2. Do differential update to catch new items since last run

        Args:
            token: Bearer token for authentication.
            max_concurrent: Maximum concurrent API requests.
        """
        # Try to load from disk first
        if self._load_from_disk():
            # Do differential update to catch new items
            await self._differential_update(token, max_concurrent=max_concurrent)
        else:
            # No persisted index, do full build
            await self.rebuild_index(token, max_concurrent=max_concurrent)

    async def rebuild_index(
        self,
        token: str,
        *,
        max_concurrent: int = 10,
    ) -> IndexStatus:
        """Full rebuild of the serial number index.

        Fetches ALL items from Homebox and rebuilds the index from scratch.
        This is slower than differential update but ensures complete accuracy.

        Args:
            token: Bearer token for authentication.
            max_concurrent: Maximum concurrent API requests.

        Returns:
            Updated index status.
        """
        logger.info("Starting full rebuild of duplicate index...")

        # Clear existing state
        self._serial_index = {}
        self._known_item_ids = set()
        self._highest_asset_id = 0
        self._total_items = 0

        # Fetch all items
        try:
            item_summaries = await self._client.list_items(token)
        except Exception as e:
            logger.error(f"Failed to fetch items for index rebuild: {e}")
            raise RuntimeError(f"Failed to fetch items from Homebox: {e}") from e

        if not item_summaries:
            logger.info("No items in Homebox, index is empty")
            self._last_build_time = datetime.now(timezone.utc)
            self._last_update_time = self._last_build_time
            self._is_loaded = True
            self._save_to_disk()
            return self.get_status()

        self._total_items = len(item_summaries)

        # Track highest asset ID from summaries
        for item in item_summaries:
            asset_id = self.parse_asset_id(item.get("assetId"))
            if asset_id > self._highest_asset_id:
                self._highest_asset_id = asset_id
            item_id = item.get("id")
            if item_id:
                self._known_item_ids.add(item_id)

        # Fetch details for all items in parallel
        await self._fetch_and_index_items(
            token,
            item_summaries,
            max_concurrent=max_concurrent,
        )

        # Update timestamps
        self._last_build_time = datetime.now(timezone.utc)
        self._last_update_time = self._last_build_time
        self._is_loaded = True

        # Persist to disk
        self._save_to_disk()

        logger.info(
            f"Index rebuild complete: {len(self._serial_index)} items with serials "
            f"out of {self._total_items} total items"
        )
        return self.get_status()

    async def _differential_update(
        self,
        token: str,
        *,
        max_concurrent: int = 10,
    ) -> int:
        """Update index with only new items (items with higher asset IDs).

        Args:
            token: Bearer token for authentication.
            max_concurrent: Maximum concurrent API requests.

        Returns:
            Number of new items processed.
        """
        logger.debug(
            f"Starting differential update (highest known asset ID: {self._highest_asset_id})"
        )

        # Fetch all items to compare
        try:
            item_summaries = await self._client.list_items(token)
        except Exception as e:
            logger.warning(f"Failed to fetch items for differential update: {e}")
            return 0

        if not item_summaries:
            return 0

        # Find new items (asset ID > highest known OR item ID not in known set)
        new_items = []
        for item in item_summaries:
            item_id = item.get("id")
            asset_id = self.parse_asset_id(item.get("assetId"))

            # Item is new if:
            # 1. Its asset ID is higher than our highest known, OR
            # 2. Its item ID is not in our known set (handles items added outside normal flow)
            if asset_id > self._highest_asset_id or item_id not in self._known_item_ids:
                new_items.append(item)

                # Track this item
                if item_id:
                    self._known_item_ids.add(item_id)
                if asset_id > self._highest_asset_id:
                    self._highest_asset_id = asset_id

        if not new_items:
            logger.debug("No new items found in differential update")
            return 0

        logger.info(f"Found {len(new_items)} new items since last update")

        # Update total count
        self._total_items = len(item_summaries)

        # Fetch details for new items only
        await self._fetch_and_index_items(
            token,
            new_items,
            max_concurrent=max_concurrent,
        )

        # Update timestamp and persist
        self._last_update_time = datetime.now(timezone.utc)
        self._save_to_disk()

        return len(new_items)

    async def _fetch_and_index_items(
        self,
        token: str,
        items: list[dict],
        *,
        max_concurrent: int = 10,
    ) -> None:
        """Fetch item details and add to index.

        Args:
            token: Bearer token for authentication.
            items: List of item summaries to fetch details for.
            max_concurrent: Maximum concurrent requests.
        """
        if not items:
            return

        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_item_detail(item_id: str) -> dict | None:
            """Fetch single item detail with rate limiting."""
            async with semaphore:
                try:
                    return await self._client.get_item(token, item_id)
                except Exception as e:
                    logger.trace(f"Failed to fetch item {item_id}: {e}")
                    return None

        # Extract IDs and fetch all details concurrently
        item_ids = [item.get("id") for item in items if item.get("id")]
        tasks = [fetch_item_detail(item_id) for item_id in item_ids]

        logger.debug(f"Fetching details for {len(tasks)} items...")
        item_details = await asyncio.gather(*tasks, return_exceptions=True)

        # Add to index
        for detail in item_details:
            if isinstance(detail, Exception) or not detail:
                continue
            self._add_detail_to_index(detail)

    def _add_detail_to_index(self, detail: dict) -> bool:
        """Add a single item detail to the index.

        Args:
            detail: Full item detail from API.

        Returns:
            True if item had a serial number and was indexed.
        """
        serial = self.normalize_serial(detail.get("serialNumber"))
        if not serial:
            return False

        location = detail.get("location") or {}
        self._serial_index[serial] = ExistingItem(
            id=detail.get("id", ""),
            name=detail.get("name", "Unknown"),
            serial_number=serial,
            asset_id=self.parse_asset_id(detail.get("assetId")),
            location_id=location.get("id"),
            location_name=location.get("name"),
        )
        return True

    def add_item_to_index(self, item: dict) -> bool:
        """Add a newly created item to the index.

        Call this after successfully creating an item in Homebox to keep
        the index up-to-date without a full rebuild.

        Args:
            item: Item data (from creation response or detection).
                  Must have 'id' and optionally 'serialNumber'/'serial_number'.

        Returns:
            True if item was added to index (had serial number).
        """
        item_id = item.get("id")
        if item_id:
            self._known_item_ids.add(item_id)

        asset_id = self.parse_asset_id(item.get("assetId") or item.get("asset_id"))
        if asset_id > self._highest_asset_id:
            self._highest_asset_id = asset_id

        self._total_items += 1

        # Get serial number (support both cases)
        serial = item.get("serialNumber") or item.get("serial_number")
        normalized = self.normalize_serial(serial)

        if not normalized:
            return False

        location = item.get("location") or {}
        self._serial_index[normalized] = ExistingItem(
            id=item_id or "",
            name=item.get("name", "Unknown"),
            serial_number=normalized,
            asset_id=asset_id,
            location_id=location.get("id"),
            location_name=location.get("name"),
        )

        self._last_update_time = datetime.now(timezone.utc)

        # Save periodically (every 10 items or so, handled by caller)
        logger.debug(f"Added item to index: {item.get('name')} (serial: {normalized})")
        return True

    def save(self) -> None:
        """Explicitly save the index to disk.

        Call this after batch operations to persist changes.
        """
        self._save_to_disk()

    async def find_duplicates(
        self,
        token: str,
        items: list[dict],
        *,
        ensure_loaded: bool = True,
    ) -> list[DuplicateMatch]:
        """Find potential duplicates by checking serial numbers.

        Args:
            token: Bearer token for authentication.
            items: List of item dicts to check (must have 'serial_number' or 'serialNumber').
            ensure_loaded: If True and index not loaded, load/build first.

        Returns:
            List of DuplicateMatch objects for items with matching serials.
        """
        # Ensure index is loaded
        if ensure_loaded and not self._is_loaded:
            await self.load_or_build(token)

        if not self._serial_index:
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

            if normalized in self._serial_index:
                existing = self._serial_index[normalized]
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
        """Clear the in-memory index.

        The persisted index on disk is NOT deleted. Call rebuild_index()
        for a fresh start, or delete the index file manually.
        """
        self._serial_index = {}
        self._known_item_ids = set()
        self._highest_asset_id = 0
        self._total_items = 0
        self._is_loaded = False
        logger.debug("In-memory serial number index cleared")
