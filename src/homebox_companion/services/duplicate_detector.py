"""Duplicate detection service for preventing duplicate items.

This service checks for potential duplicate items using multiple strategies:
1. Serial number matching (exact, normalized)
2. Manufacturer + Model number matching (exact)
3. Fuzzy name matching (similarity threshold)

The multi-strategy approach helps catch duplicates even when:
- AI misreads serial numbers (e.g., adding extra digits)
- Serial numbers are not available
- Items are entered with slight name variations

Features:
- Persistent index storage (survives restarts)
- Differential updates using asset IDs (only fetch new items)
- Manual rebuild capability
- Incremental updates when items are created
- Uses export endpoint for efficient bulk data retrieval

Note: The Homebox API's /items list endpoint returns ItemSummary which does NOT
include serialNumber. This service uses the /items/export endpoint for efficient
bulk retrieval of all item data including serial numbers, manufacturers, and models.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..core.config import settings

if TYPE_CHECKING:
    from ..homebox import HomeboxClient


# Default path for persisted index
INDEX_FILE = Path(settings.data_dir) / "duplicate_index.json"

# Fuzzy matching threshold (0.0 to 1.0) - names must be this similar to match
# 0.85 means 85% similar, catches typos and minor variations
DEFAULT_NAME_SIMILARITY_THRESHOLD = 0.85

# Minimum name length for fuzzy matching (avoid matching short generic names)
MIN_NAME_LENGTH_FOR_FUZZY = 5


class MatchType(Enum):
    """Type of duplicate match found."""

    SERIAL_NUMBER = "serial_number"
    """Exact serial number match (highest confidence)."""

    MANUFACTURER_MODEL = "manufacturer_model"
    """Same manufacturer + model number (high confidence)."""

    FUZZY_NAME = "fuzzy_name"
    """Similar item name (medium confidence, may be false positive)."""


@dataclass
class ExistingItem:
    """Summary of an existing item in Homebox."""

    id: str
    name: str
    serial_number: str
    asset_id: int = 0
    location_id: str | None = None
    location_name: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None

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
            manufacturer=data.get("manufacturer"),
            model_number=data.get("model_number"),
        )


@dataclass
class DuplicateMatch:
    """A match between a new item and an existing item."""

    item_index: int
    """Index of the new item in the submitted list."""

    item_name: str
    """Name of the new item."""

    existing_item: ExistingItem
    """The existing item that matches."""

    match_type: MatchType
    """How the duplicate was detected."""

    match_value: str
    """The value that matched (serial, manufacturer+model, or name)."""

    similarity_score: float = 1.0
    """Similarity score (1.0 for exact matches, 0.0-1.0 for fuzzy)."""

    @property
    def confidence(self) -> str:
        """Human-readable confidence level."""
        if self.match_type == MatchType.SERIAL_NUMBER:
            return "high"
        elif self.match_type == MatchType.MANUFACTURER_MODEL:
            return "high"
        else:
            if self.similarity_score >= 0.95:
                return "medium-high"
            elif self.similarity_score >= 0.90:
                return "medium"
            else:
                return "low"


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

    items_with_model: int
    """Number of items with manufacturer+model in index."""

    highest_asset_id: int
    """Highest asset ID seen (for differential updates)."""

    is_loaded: bool
    """Whether the index is currently loaded in memory."""


class DuplicateDetector:
    """Detects potential duplicate items using multiple strategies.

    This service helps prevent accidentally adding duplicate items to Homebox
    by checking against existing inventory using:
    1. Serial number matching (exact, normalized)
    2. Manufacturer + Model number matching (exact)
    3. Fuzzy name matching (similarity threshold)

    Features:
    - Multi-strategy duplicate detection
    - Builds index on first use or startup
    - Persists index to disk for fast restarts
    - Differential updates using asset IDs
    - Manual rebuild and incremental update support
    - Uses export endpoint for efficient bulk retrieval

    Usage:
        detector = DuplicateDetector(homebox_client)

        # Load persisted index (fast) then update with new items
        await detector.load_or_build(token)

        # Check for duplicates (returns matches with type and confidence)
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
        name_similarity_threshold: float = DEFAULT_NAME_SIMILARITY_THRESHOLD,
    ) -> None:
        """Initialize the duplicate detector.

        Args:
            client: The HomeboxClient instance for API calls.
            index_path: Path to store persistent index. Defaults to config dir.
            name_similarity_threshold: Minimum similarity (0.0-1.0) for fuzzy name matching.
        """
        self._client = client
        self._index_path = index_path or INDEX_FILE
        self._name_similarity_threshold = name_similarity_threshold

        # In-memory index state
        # Primary index: normalized serial number -> item
        self._serial_index: dict[str, ExistingItem] = {}

        # Secondary index: normalized "manufacturer|model" -> item
        self._model_index: dict[str, ExistingItem] = {}

        # Tertiary index: all items for fuzzy name matching
        self._all_items: list[ExistingItem] = []

        # Tracking state
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

    @staticmethod
    def normalize_manufacturer_model(manufacturer: str | None, model: str | None) -> str | None:
        """Create a normalized key from manufacturer and model number.

        Args:
            manufacturer: The manufacturer name.
            model: The model number.

        Returns:
            Normalized "MANUFACTURER|MODEL" key or None if either is empty.
        """
        if not manufacturer or not model:
            return None
        mfr = manufacturer.strip().upper()
        mdl = model.strip().upper()
        if not mfr or not mdl:
            return None
        return f"{mfr}|{mdl}"

    @staticmethod
    def normalize_name(name: str | None) -> str | None:
        """Normalize a name for comparison.

        Args:
            name: The item name to normalize.

        Returns:
            Lowercase, trimmed name with extra whitespace removed, or None if empty.
        """
        if not name:
            return None
        # Lowercase, strip, collapse multiple spaces
        normalized = " ".join(name.lower().split())
        return normalized if normalized else None

    @staticmethod
    def compute_name_similarity(name1: str, name2: str) -> float:
        """Compute similarity ratio between two names.

        Uses SequenceMatcher for fuzzy matching which handles:
        - Typos and character transpositions
        - Minor word variations
        - Partial matches

        Args:
            name1: First name to compare.
            name2: Second name to compare.

        Returns:
            Similarity ratio from 0.0 (completely different) to 1.0 (identical).
        """
        # Normalize both names for comparison
        n1 = " ".join(name1.lower().split())
        n2 = " ".join(name2.lower().split())
        return SequenceMatcher(None, n1, n2).ratio()

    def get_status(self) -> IndexStatus:
        """Get current index status."""
        return IndexStatus(
            last_build_time=self._last_build_time.isoformat() if self._last_build_time else None,
            last_update_time=self._last_update_time.isoformat() if self._last_update_time else None,
            total_items_indexed=self._total_items,
            items_with_serials=len(self._serial_index),
            items_with_model=len(self._model_index),
            highest_asset_id=self._highest_asset_id,
            is_loaded=self._is_loaded,
        )

    def _parse_export_csv(self, csv_data: str) -> list[dict[str, Any]]:
        """Parse CSV export data from Homebox.

        CSV columns from Homebox export:
        HB.import_ref, HB.location, HB.labels, HB.asset_id, HB.archived, HB.url,
        HB.name, HB.quantity, HB.description, HB.insured, HB.notes, HB.purchase_price,
        HB.purchase_from, HB.purchase_time, HB.manufacturer, HB.model_number,
        HB.serial_number, HB.lifetime_warranty, HB.warranty_expires, HB.warranty_details,
        HB.sold_to, HB.sold_price, HB.sold_time, HB.sold_notes

        Args:
            csv_data: Raw CSV string from export endpoint.

        Returns:
            List of dicts with normalized field names.
        """
        items = []
        reader = csv.DictReader(io.StringIO(csv_data))

        for row in reader:
            # Extract item ID from URL (last path segment)
            url = row.get("HB.url", "")
            item_id = url.split("/")[-1] if url else ""

            items.append({
                "id": item_id,
                "name": row.get("HB.name", ""),
                "serial_number": row.get("HB.serial_number", ""),
                "manufacturer": row.get("HB.manufacturer", ""),
                "model_number": row.get("HB.model_number", ""),
                "asset_id": row.get("HB.asset_id", ""),
                "location": row.get("HB.location", ""),
                "description": row.get("HB.description", ""),
            })

        return items

    def _add_to_all_indices(self, item_data: dict[str, Any]) -> None:
        """Add an item to all applicable indices.

        Args:
            item_data: Item dict with id, name, serial_number, manufacturer,
                      model_number, asset_id, location.
        """
        item_id = item_data.get("id", "")
        name = item_data.get("name", "Unknown")
        serial = self.normalize_serial(item_data.get("serial_number"))
        manufacturer = item_data.get("manufacturer")
        model = item_data.get("model_number")
        asset_id = self.parse_asset_id(item_data.get("asset_id"))
        location = item_data.get("location")

        # Track item ID and highest asset ID
        if item_id:
            self._known_item_ids.add(item_id)
        if asset_id > self._highest_asset_id:
            self._highest_asset_id = asset_id

        # Create ExistingItem
        existing_item = ExistingItem(
            id=item_id,
            name=name,
            serial_number=serial or "",
            asset_id=asset_id,
            location_id=None,  # Not available from CSV
            location_name=location,
            manufacturer=manufacturer,
            model_number=model,
        )

        # Add to serial index if serial exists
        if serial:
            self._serial_index[serial] = existing_item

        # Add to model index if manufacturer and model exist
        model_key = self.normalize_manufacturer_model(manufacturer, model)
        if model_key:
            self._model_index[model_key] = existing_item

        # Always add to all_items for fuzzy name matching
        self._all_items.append(existing_item)

    def _save_to_disk(self) -> None:
        """Persist index to disk."""
        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": 2,  # Bumped for multi-index support
                "last_build_time": self._last_build_time.isoformat() if self._last_build_time else None,
                "last_update_time": self._last_update_time.isoformat() if self._last_update_time else None,
                "highest_asset_id": self._highest_asset_id,
                "total_items": self._total_items,
                "known_item_ids": list(self._known_item_ids),
                "serial_index": {
                    serial: item.to_dict()
                    for serial, item in self._serial_index.items()
                },
                "model_index": {
                    key: item.to_dict()
                    for key, item in self._model_index.items()
                },
                "all_items": [item.to_dict() for item in self._all_items],
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

            # Check version compatibility - version 2 required for multi-index support
            version = data.get("version", 0)
            if version < 2:
                logger.info("Duplicate index version 1 detected, will rebuild for multi-index support")
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

            # Restore model index
            self._model_index = {
                key: ExistingItem.from_dict(item_data)
                for key, item_data in data.get("model_index", {}).items()
            }

            # Restore all items list for fuzzy name matching
            self._all_items = [
                ExistingItem.from_dict(item_data)
                for item_data in data.get("all_items", [])
            ]

            self._is_loaded = True
            logger.info(
                f"Loaded duplicate index from disk: {len(self._serial_index)} serials, "
                f"{len(self._model_index)} models, {len(self._all_items)} items for name matching, "
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
        """Full rebuild of all duplicate detection indices.

        Uses the /items/export endpoint for efficient bulk retrieval of all
        item data in a single API call. Builds three indices:
        1. Serial number index (exact match)
        2. Manufacturer+Model index (exact match)
        3. All items list (for fuzzy name matching)

        Args:
            token: Bearer token for authentication.
            max_concurrent: Maximum concurrent API requests (unused with export).

        Returns:
            Updated index status.
        """
        logger.info("Starting full rebuild of duplicate index using export endpoint...")

        # Clear existing state
        self._serial_index = {}
        self._model_index = {}
        self._all_items = []
        self._known_item_ids = set()
        self._highest_asset_id = 0
        self._total_items = 0

        # Fetch all items via export endpoint (single API call!)
        try:
            csv_data = await self._client.export_items(token)
        except Exception as e:
            logger.error(f"Failed to export items for index rebuild: {e}")
            raise RuntimeError(f"Failed to export items from Homebox: {e}") from e

        # Parse CSV and build indices
        items_parsed = self._parse_export_csv(csv_data)

        if not items_parsed:
            logger.info("No items in Homebox, index is empty")
            self._last_build_time = datetime.now(timezone.utc)
            self._last_update_time = self._last_build_time
            self._is_loaded = True
            self._save_to_disk()
            return self.get_status()

        self._total_items = len(items_parsed)

        # Build all indices from parsed items
        for item_data in items_parsed:
            self._add_to_all_indices(item_data)

        # Update timestamps
        self._last_build_time = datetime.now(timezone.utc)
        self._last_update_time = self._last_build_time
        self._is_loaded = True

        # Persist to disk
        self._save_to_disk()

        logger.info(
            f"Index rebuild complete: {len(self._serial_index)} serials, "
            f"{len(self._model_index)} models, {len(self._all_items)} items "
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
            response = await self._client.list_items(token)
            # list_items returns paginated response: {items: [...], page, pageSize, total}
            item_summaries = response.get("items", [])
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
        """Add a single item detail to all indices.

        Args:
            detail: Full item detail from API.

        Returns:
            True if item was indexed (always True for valid items).
        """
        item_id = detail.get("id", "")
        name = detail.get("name", "Unknown")
        serial = self.normalize_serial(detail.get("serialNumber"))
        manufacturer = detail.get("manufacturer")
        model = detail.get("modelNumber")
        location = detail.get("location") or {}

        # Create ExistingItem
        existing_item = ExistingItem(
            id=item_id,
            name=name,
            serial_number=serial or "",
            asset_id=self.parse_asset_id(detail.get("assetId")),
            location_id=location.get("id") if isinstance(location, dict) else None,
            location_name=location.get("name") if isinstance(location, dict) else None,
            manufacturer=manufacturer,
            model_number=model,
        )

        # Add to serial index if serial exists
        if serial:
            self._serial_index[serial] = existing_item

        # Add to model index if manufacturer and model exist
        model_key = self.normalize_manufacturer_model(manufacturer, model)
        if model_key:
            self._model_index[model_key] = existing_item

        # Always add to all_items for fuzzy name matching
        self._all_items.append(existing_item)

        return True

    def add_item_to_index(self, item: dict) -> bool:
        """Add a newly created item to all indices.

        Call this after successfully creating an item in Homebox to keep
        the indices up-to-date without a full rebuild.

        Args:
            item: Item data (from creation response or detection).
                  Should have 'id', 'name', and optionally 'serialNumber',
                  'manufacturer', 'modelNumber'.

        Returns:
            True if item was added to any index (always True for valid items).
        """
        item_id = item.get("id")
        if item_id:
            self._known_item_ids.add(item_id)

        asset_id = self.parse_asset_id(item.get("assetId") or item.get("asset_id"))
        if asset_id > self._highest_asset_id:
            self._highest_asset_id = asset_id

        self._total_items += 1

        # Get item data (support both camelCase and snake_case)
        name = item.get("name", "Unknown")
        serial = item.get("serialNumber") or item.get("serial_number")
        manufacturer = item.get("manufacturer")
        model = item.get("modelNumber") or item.get("model_number")
        location = item.get("location") or {}

        normalized_serial = self.normalize_serial(serial)

        # Create ExistingItem
        existing_item = ExistingItem(
            id=item_id or "",
            name=name,
            serial_number=normalized_serial or "",
            asset_id=asset_id,
            location_id=location.get("id") if isinstance(location, dict) else None,
            location_name=location.get("name") if isinstance(location, dict) else location,
            manufacturer=manufacturer,
            model_number=model,
        )

        # Add to serial index if serial exists
        if normalized_serial:
            self._serial_index[normalized_serial] = existing_item

        # Add to model index if manufacturer and model exist
        model_key = self.normalize_manufacturer_model(manufacturer, model)
        if model_key:
            self._model_index[model_key] = existing_item

        # Always add to all_items for fuzzy name matching
        self._all_items.append(existing_item)

        self._last_update_time = datetime.now(timezone.utc)

        # Log what was indexed
        indexed = []
        if normalized_serial:
            indexed.append(f"serial: {normalized_serial}")
        if model_key:
            indexed.append(f"model: {model_key}")
        indexed.append("name")

        logger.debug(f"Added item to index: '{name}' ({', '.join(indexed)})")
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
        check_serial: bool = True,
        check_model: bool = True,
        check_name: bool = True,
    ) -> list[DuplicateMatch]:
        """Find potential duplicates using multiple detection strategies.

        Checks for duplicates using three strategies (in order of confidence):
        1. Serial number matching (exact, highest confidence)
        2. Manufacturer + Model matching (exact, high confidence)
        3. Fuzzy name matching (similarity threshold, medium confidence)

        Args:
            token: Bearer token for authentication.
            items: List of item dicts to check.
            ensure_loaded: If True and index not loaded, load/build first.
            check_serial: Enable serial number matching.
            check_model: Enable manufacturer+model matching.
            check_name: Enable fuzzy name matching.

        Returns:
            List of DuplicateMatch objects with match type and confidence.
        """
        # Ensure index is loaded
        if ensure_loaded and not self._is_loaded:
            await self.load_or_build(token)

        if not self._all_items:
            logger.debug("No existing items in index, skipping duplicate check")
            return []

        matches: list[DuplicateMatch] = []
        # Track which items already matched (to avoid duplicate matches)
        matched_existing_ids: set[str] = set()

        for i, item in enumerate(items):
            item_name = item.get("name", "Unknown")
            item_matched_ids: set[str] = set()  # Track matches for this item

            # Strategy 1: Serial number matching (highest confidence)
            if check_serial:
                serial = item.get("serial_number") or item.get("serialNumber")
                normalized_serial = self.normalize_serial(serial)

                if normalized_serial and normalized_serial in self._serial_index:
                    existing = self._serial_index[normalized_serial]
                    if existing.id not in item_matched_ids:
                        matches.append(
                            DuplicateMatch(
                                item_index=i,
                                item_name=item_name,
                                existing_item=existing,
                                match_type=MatchType.SERIAL_NUMBER,
                                match_value=normalized_serial,
                                similarity_score=1.0,
                            )
                        )
                        item_matched_ids.add(existing.id)
                        logger.warning(
                            f"Serial match: '{item_name}' serial '{normalized_serial}' "
                            f"matches '{existing.name}' (ID: {existing.id})"
                        )

            # Strategy 2: Manufacturer + Model matching (high confidence)
            if check_model:
                manufacturer = item.get("manufacturer")
                model = item.get("model_number") or item.get("modelNumber")
                model_key = self.normalize_manufacturer_model(manufacturer, model)

                if model_key and model_key in self._model_index:
                    existing = self._model_index[model_key]
                    if existing.id not in item_matched_ids:
                        matches.append(
                            DuplicateMatch(
                                item_index=i,
                                item_name=item_name,
                                existing_item=existing,
                                match_type=MatchType.MANUFACTURER_MODEL,
                                match_value=model_key,
                                similarity_score=1.0,
                            )
                        )
                        item_matched_ids.add(existing.id)
                        logger.warning(
                            f"Model match: '{item_name}' ({model_key}) "
                            f"matches '{existing.name}' (ID: {existing.id})"
                        )

            # Strategy 3: Fuzzy name matching (medium confidence)
            if check_name and len(item_name) >= MIN_NAME_LENGTH_FOR_FUZZY:
                for existing in self._all_items:
                    if existing.id in item_matched_ids:
                        continue  # Already matched via serial or model

                    if len(existing.name) < MIN_NAME_LENGTH_FOR_FUZZY:
                        continue  # Skip short names

                    similarity = self.compute_name_similarity(item_name, existing.name)
                    if similarity >= self._name_similarity_threshold:
                        matches.append(
                            DuplicateMatch(
                                item_index=i,
                                item_name=item_name,
                                existing_item=existing,
                                match_type=MatchType.FUZZY_NAME,
                                match_value=existing.name,
                                similarity_score=similarity,
                            )
                        )
                        item_matched_ids.add(existing.id)
                        logger.info(
                            f"Name match ({similarity:.0%}): '{item_name}' "
                            f"similar to '{existing.name}' (ID: {existing.id})"
                        )

        # Summary logging
        serial_matches = sum(1 for m in matches if m.match_type == MatchType.SERIAL_NUMBER)
        model_matches = sum(1 for m in matches if m.match_type == MatchType.MANUFACTURER_MODEL)
        name_matches = sum(1 for m in matches if m.match_type == MatchType.FUZZY_NAME)

        logger.info(
            f"Duplicate check complete: {len(matches)} potential duplicates "
            f"({serial_matches} serial, {model_matches} model, {name_matches} name)"
        )
        return matches

    def clear_cache(self) -> None:
        """Clear all in-memory indices.

        The persisted index on disk is NOT deleted. Call rebuild_index()
        for a fresh start, or delete the index file manually.
        """
        self._serial_index = {}
        self._model_index = {}
        self._all_items = []
        self._known_item_ids = set()
        self._highest_asset_id = 0
        self._total_items = 0
        self._is_loaded = False
        logger.debug("In-memory duplicate indices cleared")
