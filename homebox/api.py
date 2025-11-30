"""Core API client for Homebox.

This module provides a clean, requests-like interface for interacting
with the Homebox API.

Example:
    >>> import homebox
    >>> with homebox.Session() as hb:
    ...     locations = hb.locations()
    ...     item = hb.create_item("Hammer", location=locations[0])
    ...     print(f"Created: {item.name}")
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import requests

from ._logging import logger
from .types import Item, Label, Location

if TYPE_CHECKING:
    from types import TracebackType

# Default API endpoint
DEMO_URL = "https://demo.homebox.software/api/v1"

# Default credentials for the demo environment
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo"

# Browser-style headers to avoid being blocked
_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://demo.homebox.software",
    "Referer": "https://demo.homebox.software/",
    "Connection": "keep-alive",
    "DNT": "1",
    "Sec-GPC": "1",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}


class HomeboxError(Exception):
    """Base exception for Homebox API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response: requests.Response | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AuthenticationError(HomeboxError):
    """Raised when authentication fails."""


def _to_iso_string(value: str | date | datetime | None) -> str | None:
    """Convert a date/datetime to ISO string format."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


class Session:
    """A Homebox API session with automatic authentication.

    This class provides a clean, context-manager-friendly interface for
    interacting with the Homebox API. It handles authentication automatically
    and provides intuitive methods for common operations.

    Args:
        url: Base URL for the Homebox API.
        email: Login email (defaults to demo credentials).
        password: Login password (defaults to demo credentials).
        token: Pre-existing auth token (skips login if provided).
        auto_login: Whether to login automatically on first request.

    Example:
        >>> with homebox.Session() as hb:
        ...     items = hb.items()
        ...     for item in items[:5]:
        ...         print(item.name)

        >>> # Or without context manager
        >>> hb = homebox.Session()
        >>> hb.login()
        >>> locations = hb.locations()
    """

    def __init__(
        self,
        url: str = DEMO_URL,
        *,
        email: str = DEMO_EMAIL,
        password: str = DEMO_PASSWORD,
        token: str | None = None,
        auto_login: bool = True,
    ) -> None:
        self.url = url.rstrip("/")
        self._email = email
        self._password = password
        self._token: str | None = token
        self._auto_login = auto_login
        self._session = requests.Session()
        self._session.headers.update(_DEFAULT_HEADERS)

    def __enter__(self) -> Session:
        """Enter context manager, optionally logging in."""
        if self._auto_login and not self._token:
            self.login()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager and close session."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()
        logger.debug("Session closed")

    @property
    def token(self) -> str | None:
        """The current authentication token."""
        return self._token

    @property
    def is_authenticated(self) -> bool:
        """Whether the session has a valid token."""
        return self._token is not None

    def login(self, email: str | None = None, password: str | None = None) -> Session:
        """Authenticate with the Homebox API.

        Args:
            email: Override the default email.
            password: Override the default password.

        Returns:
            Self for method chaining.

        Raises:
            AuthenticationError: If login fails.
        """
        email = email or self._email
        password = password or self._password

        logger.debug("Logging in as {}", email)

        response = self._session.post(
            f"{self.url}/users/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": email, "password": password, "stayLoggedIn": True},
            timeout=20,
        )

        if not response.ok:
            logger.error("Login failed with status {}", response.status_code)
            raise AuthenticationError(
                f"Login failed: {response.status_code}",
                status_code=response.status_code,
                response=response,
            )

        data = response.json()
        self._token = data.get("token") or data.get("jwt") or data.get("accessToken")

        if not self._token:
            raise AuthenticationError("Login response did not include a token")

        logger.info("Successfully authenticated as {}", email)
        return self

    def _ensure_auth(self) -> None:
        """Ensure we have a valid token, logging in if needed."""
        if not self._token:
            if self._auto_login:
                self.login()
            else:
                raise AuthenticationError("Not authenticated. Call login() first.")

    def _auth_headers(self) -> dict[str, str]:
        """Get headers with authentication."""
        self._ensure_auth()
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated request."""
        kwargs.setdefault("headers", self._auth_headers())
        kwargs.setdefault("timeout", 20)

        url = f"{self.url}{endpoint}"
        logger.debug("{} {}", method.upper(), endpoint)

        response = self._session.request(method, url, **kwargs)

        if not response.ok:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            logger.error("{} {} failed: {}", method.upper(), endpoint, detail)
            raise HomeboxError(
                f"{method.upper()} {endpoint} failed: {response.status_code}",
                status_code=response.status_code,
                response=response,
            )

        return response

    # -------------------------------------------------------------------------
    # Locations
    # -------------------------------------------------------------------------

    def locations(self, *, include_children: bool = True) -> list[Location]:
        """Get all locations.

        Args:
            include_children: Whether to include child locations.

        Returns:
            List of Location objects.
        """
        params = None
        if not include_children:
            params = {"filterChildren": "true"}

        response = self._request("GET", "/locations", params=params)
        locations = Location.from_list(response.json())
        logger.debug("Fetched {} locations", len(locations))
        return locations

    def location(self, location_id: str) -> Location:
        """Get a single location by ID.

        Args:
            location_id: The location ID.

        Returns:
            Location object.
        """
        response = self._request("GET", f"/locations/{location_id}")
        return Location.from_dict(response.json())

    # -------------------------------------------------------------------------
    # Labels
    # -------------------------------------------------------------------------

    def labels(self) -> list[Label]:
        """Get all labels.

        Returns:
            List of Label objects.
        """
        response = self._request("GET", "/labels")
        labels = Label.from_list(response.json())
        logger.debug("Fetched {} labels", len(labels))
        return labels

    # -------------------------------------------------------------------------
    # Items
    # -------------------------------------------------------------------------

    def items(self) -> list[Item]:
        """Get all items.

        Returns:
            List of Item objects.
        """
        response = self._request("GET", "/items")
        data = response.json()
        # API returns {"items": [...]} wrapper
        raw_items = data.get("items", data) if isinstance(data, dict) else data
        items = Item.from_list(raw_items)
        logger.debug("Fetched {} items", len(items))
        return items

    def item(self, item_id: str) -> Item:
        """Get a single item by ID.

        Args:
            item_id: The item ID.

        Returns:
            Item object.
        """
        response = self._request("GET", f"/items/{item_id}")
        return Item.from_dict(response.json())

    def create_item(
        self,
        name: str | Item,
        *,
        quantity: int = 1,
        description: str | None = None,
        location: str | Location | None = None,
        labels: Iterable[str | Label] | None = None,
    ) -> Item:
        """Create a new item.

        Args:
            name: Item name, or an Item object.
            quantity: Number of items.
            description: Optional description.
            location: Location ID or Location object.
            labels: List of label IDs or Label objects.

        Returns:
            The created Item with its new ID.

        Example:
            >>> item = hb.create_item("Screwdriver", quantity=3, location="loc-123")
            >>> print(item.id)
        """
        if isinstance(name, Item):
            item = name
        else:
            location_id = location.id if isinstance(location, Location) else location
            label_ids = None
            if labels:
                label_ids = [lbl.id if isinstance(lbl, Label) else lbl for lbl in labels]

            item = Item(
                name=name,
                quantity=quantity,
                description=description,
                location_id=location_id,
                label_ids=label_ids or None,
            )

        payload = item.to_api_payload()
        logger.debug("Creating item: {}", item.name)
        response = self._request("POST", "/items", json=payload)
        created = Item.from_dict(response.json())
        logger.info("Created item '{}' with id {}", created.name, created.id)
        return created

    def create_items(self, items: Iterable[Item]) -> list[Item]:
        """Create multiple items.

        Args:
            items: Items to create.

        Returns:
            List of created Items with their IDs.
        """
        created: list[Item] = []
        for item in items:
            created.append(self.create_item(item))
        return created

    def update_item(
        self,
        item_id: str,
        *,
        # Basic info
        name: str | None = None,
        description: str | None = None,
        quantity: int | None = None,
        # Organization
        location: str | Location | None = None,
        labels: Iterable[str | Label] | None = None,
        parent: str | Item | None = None,
        # Status flags
        archived: bool | None = None,
        insured: bool | None = None,
        # Identification
        asset_id: str | None = None,
        serial_number: str | None = None,
        model_number: str | None = None,
        manufacturer: str | None = None,
        # Purchase info
        purchase_from: str | None = None,
        purchase_price: float | None = None,
        purchase_time: str | date | datetime | None = None,
        # Sale info
        sold_to: str | None = None,
        sold_price: float | None = None,
        sold_time: str | date | datetime | None = None,
        sold_notes: str | None = None,
        # Warranty
        lifetime_warranty: bool | None = None,
        warranty_expires: str | date | datetime | None = None,
        warranty_details: str | None = None,
        # Extras
        notes: str | None = None,
        fields: list[dict[str, Any]] | None = None,
        # Sync
        sync_child_locations: bool | None = None,
    ) -> Item:
        """Update an existing item.

        Only the provided fields will be updated. All parameters are optional.

        Args:
            item_id: The item ID to update.

            name: Item name (1-255 characters).
            description: Item description (max 1000 characters).
            quantity: Number of items.

            location: New location (ID or Location object).
            labels: New labels (list of IDs or Label objects).
            parent: Parent item (ID or Item object).

            archived: Whether the item is archived.
            insured: Whether the item is insured.

            asset_id: Custom asset identifier.
            serial_number: Serial number.
            model_number: Model number.
            manufacturer: Manufacturer name.

            purchase_from: Where the item was purchased.
            purchase_price: Purchase price.
            purchase_time: Purchase date/time.

            sold_to: Who the item was sold to.
            sold_price: Sale price.
            sold_time: Sale date/time.
            sold_notes: Notes about the sale.

            lifetime_warranty: Whether item has lifetime warranty.
            warranty_expires: Warranty expiration date.
            warranty_details: Warranty details/notes.

            notes: Additional notes.
            fields: Custom fields (list of field dicts).
            sync_child_locations: Sync location to child items.

        Returns:
            The updated Item.

        Example:
            >>> # Update basic info
            >>> item = hb.update_item("item-123", name="New Name", quantity=5)

            >>> # Update purchase info
            >>> item = hb.update_item(
            ...     "item-123",
            ...     purchase_from="Amazon",
            ...     purchase_price=29.99,
            ...     purchase_time="2024-01-15",
            ... )

            >>> # Archive an item
            >>> item = hb.update_item("item-123", archived=True)
        """
        payload: dict[str, Any] = {}

        # Basic info
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if quantity is not None:
            payload["quantity"] = quantity

        # Organization
        if location is not None:
            payload["locationId"] = location.id if isinstance(location, Location) else location
        if labels is not None:
            payload["labelIds"] = [
                lbl.id if isinstance(lbl, Label) else lbl for lbl in labels
            ]
        if parent is not None:
            payload["parentId"] = parent.id if isinstance(parent, Item) else parent

        # Status flags
        if archived is not None:
            payload["archived"] = archived
        if insured is not None:
            payload["insured"] = insured

        # Identification
        if asset_id is not None:
            payload["assetId"] = asset_id
        if serial_number is not None:
            payload["serialNumber"] = serial_number
        if model_number is not None:
            payload["modelNumber"] = model_number
        if manufacturer is not None:
            payload["manufacturer"] = manufacturer

        # Purchase info
        if purchase_from is not None:
            payload["purchaseFrom"] = purchase_from
        if purchase_price is not None:
            payload["purchasePrice"] = purchase_price
        if purchase_time is not None:
            payload["purchaseTime"] = _to_iso_string(purchase_time)

        # Sale info
        if sold_to is not None:
            payload["soldTo"] = sold_to
        if sold_price is not None:
            payload["soldPrice"] = sold_price
        if sold_time is not None:
            payload["soldTime"] = _to_iso_string(sold_time)
        if sold_notes is not None:
            payload["soldNotes"] = sold_notes

        # Warranty
        if lifetime_warranty is not None:
            payload["lifetimeWarranty"] = lifetime_warranty
        if warranty_expires is not None:
            payload["warrantyExpires"] = _to_iso_string(warranty_expires)
        if warranty_details is not None:
            payload["warrantyDetails"] = warranty_details

        # Extras
        if notes is not None:
            payload["notes"] = notes
        if fields is not None:
            payload["fields"] = fields
        if sync_child_locations is not None:
            payload["syncChildItemsLocations"] = sync_child_locations

        if not payload:
            logger.warning("update_item called with no fields to update")
            return self.item(item_id)

        logger.debug("Updating item {}: {}", item_id, list(payload.keys()))
        response = self._request("PUT", f"/items/{item_id}", json=payload)
        updated = Item.from_dict(response.json())
        logger.info("Updated item {}", item_id)
        return updated

    def archive_item(self, item_id: str) -> Item:
        """Archive an item.

        Args:
            item_id: The item ID to archive.

        Returns:
            The updated Item.
        """
        return self.update_item(item_id, archived=True)

    def unarchive_item(self, item_id: str) -> Item:
        """Unarchive an item.

        Args:
            item_id: The item ID to unarchive.

        Returns:
            The updated Item.
        """
        return self.update_item(item_id, archived=False)

    def delete_item(self, item_id: str) -> None:
        """Delete an item.

        Args:
            item_id: The item ID to delete.
        """
        logger.debug("Deleting item {}", item_id)
        self._request("DELETE", f"/items/{item_id}")
        logger.info("Deleted item {}", item_id)


# Backwards compatibility aliases
DEMO_BASE_URL = DEMO_URL
DEFAULT_HEADERS = _DEFAULT_HEADERS


class HomeboxDemoClient:
    """Legacy client for backwards compatibility.

    .. deprecated::
        Use :class:`Session` instead for a cleaner interface.
    """

    def __init__(
        self,
        base_url: str = DEMO_URL,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(_DEFAULT_HEADERS)

    def login(self, username: str = DEMO_EMAIL, password: str = DEMO_PASSWORD) -> str:
        """Login and return the auth token."""
        payload = {"username": username, "password": password, "stayLoggedIn": True}
        response = self.session.post(
            f"{self.base_url}/users/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
            timeout=20,
        )
        self._ensure_success(response, "Login")
        data = response.json()
        token = data.get("token") or data.get("jwt") or data.get("accessToken")
        if not token:
            raise RuntimeError("Login response did not include a token field.")
        return token

    def list_locations(
        self, token: str, *, filter_children: bool | None = None
    ) -> list[dict[str, Any]]:
        """Return all available locations."""
        params = None
        if filter_children is not None:
            params = {"filterChildren": str(filter_children).lower()}

        response = self.session.get(
            f"{self.base_url}/locations",
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
            params=params,
            timeout=20,
        )
        self._ensure_success(response, "Fetch locations")
        return response.json()

    def create_items(
        self, token: str, items: Iterable[Item]
    ) -> list[dict[str, Any]]:
        """Persist items to Homebox."""
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        created: list[dict[str, Any]] = []
        for item in items:
            response = self.session.post(
                f"{self.base_url}/items",
                headers=headers,
                json=item.to_api_payload(),
                timeout=20,
            )
            self._ensure_success(response, "Create item")
            created.append(response.json())
        return created

    def update_item(
        self, token: str, item_id: str, item_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a single item by ID."""
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = self.session.put(
            f"{self.base_url}/items/{item_id}",
            headers=headers,
            json=item_data,
            timeout=20,
        )
        self._ensure_success(response, "Update item")
        return response.json()

    @staticmethod
    def _ensure_success(response: requests.Response, context: str) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise RuntimeError(f"{context} failed with {response.status_code}: {detail}") from exc


__all__ = [
    "DEMO_URL",
    "DEMO_EMAIL",
    "DEMO_PASSWORD",
    "DEMO_BASE_URL",
    "DEFAULT_HEADERS",
    "HomeboxError",
    "AuthenticationError",
    "Session",
    "HomeboxDemoClient",
]
