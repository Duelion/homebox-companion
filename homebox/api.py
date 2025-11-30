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

    def update_item(self, item_id: str, **updates: Any) -> Item:
        """Update an existing item.

        Args:
            item_id: The item ID to update.
            **updates: Fields to update (name, quantity, description, etc.).

        Returns:
            The updated Item.

        Example:
            >>> updated = hb.update_item("item-123", name="New Name", quantity=5)
        """
        logger.debug("Updating item {}: {}", item_id, updates)
        response = self._request("PUT", f"/items/{item_id}", json=updates)
        updated = Item.from_dict(response.json())
        logger.info("Updated item {}", item_id)
        return updated

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
