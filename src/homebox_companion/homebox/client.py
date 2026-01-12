"""Async HTTP client for the Homebox API using HTTPX.

This module provides an async client for interacting with the Homebox REST API.
The sync client has been removed - use async/await throughout.
"""

from __future__ import annotations

import functools
import socket
from collections.abc import Callable
from functools import lru_cache
from typing import Any, cast

import httpx
from loguru import logger
from throttled.asyncio import RateLimiterType, Throttled, rate_limiter, store

from ..core.config import settings
from ..core.exceptions import (
    HomeboxAPIError,
    HomeboxAuthError,
    HomeboxConnectionError,
    HomeboxTimeoutError,
)
from .models import Attachment, Item, ItemCreate, Label, Location


@lru_cache
def _get_homebox_rate_limiter() -> Throttled:
    """Get or create the shared Homebox API rate limiter.

    Uses Token Bucket algorithm with 30 req/sec, burst of 10.
    This prevents overwhelming the Homebox server during bulk operations.
    """
    logger.debug("Initialized Homebox API rate limiter: 30 req/sec, burst 10")
    return Throttled(
        using=RateLimiterType.TOKEN_BUCKET.value,
        quota=rate_limiter.per_sec(30, burst=10),
        store=store.MemoryStore(),  # type: ignore[arg-type]
        timeout=30,  # Wait up to 30s for capacity
    )


def _rate_limited[F: Callable[..., Any]](func: F) -> F:
    """Decorator that applies rate limiting to Homebox mutation methods.

    This decorator ensures write operations (creates, updates, deletes) are
    throttled to prevent overwhelming the Homebox server during bulk operations.
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        await _get_homebox_rate_limiter().limit("homebox_write", cost=1)
        return await func(self, *args, **kwargs)

    return cast(F, wrapper)


# Default timeout configuration
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Browser-style headers to avoid being blocked by network protections
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def _normalize_token(token: str) -> str:
    """Remove 'Bearer ' prefix from token if present.

    Homebox v0.22.0+ returns tokens with 'Bearer ' prefix built-in.
    We strip it to maintain consistent behavior when adding
    'Bearer ' prefix in Authorization headers.

    This is backward compatible - older Homebox versions that return
    tokens without the prefix will work unchanged.
    """
    if token.startswith("Bearer "):
        return token[7:]  # len("Bearer ") == 7
    return token


class HomeboxClient:
    """Async client for the Homebox API using HTTPX AsyncClient.

    This client provides connection pooling and session management
    for asynchronous interaction with a Homebox instance.

    Args:
        base_url: The base URL of the Homebox API. Defaults to the configured API URL.
        client: Optional pre-configured HTTPX AsyncClient to use.

    Example:
        >>> async with HomeboxClient() as client:
        ...     response = await client.login("user@example.com", "password")
        ...     token = response["token"]
        ...     locations = await client.list_locations(token)
    """

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.api_url).rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self) -> HomeboxClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    @staticmethod
    def _classify_connection_error(e: Exception) -> str:
        """Classify connection errors into user-friendly messages.

        Moves friendly error logic from routes into the client layer where
        httpx exceptions are wrapped into domain exceptions.
        """
        error_str = str(e).lower()

        # DNS resolution failure
        if "getaddrinfo failed" in error_str or isinstance(
            getattr(e, "__cause__", None), socket.gaierror
        ):
            return (
                "Cannot connect to Homebox server. The server address could not be resolved. "
                "Please verify the HBC_HOMEBOX_URL is correct."
            )

        # Connection refused
        if "connection refused" in error_str or "actively refused" in error_str:
            return "Connection refused. Please check if Homebox is running and the port is correct."

        # SSL/TLS errors
        if "ssl" in error_str or "certificate" in error_str:
            return "SSL/TLS error. Please check if the server URL protocol (http/https) is correct."

        # Network unreachable
        if "network is unreachable" in error_str or "no route to host" in error_str:
            return "Network unreachable. Please check your network connection and server address."

        # Default
        return (
            "Cannot connect to Homebox server. Please check your network and server configuration."
        )

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate with Homebox and return the login response.

        Args:
            username: The user's email address.
            password: The user's password.

        Returns:
            Dictionary containing token, expiresAt, and other login response fields.

        Raises:
            HomeboxAuthError: If authentication fails.
        """
        login_url = f"{self.base_url}/users/login"
        logger.debug(f"Login: Attempting connection to {login_url}")
        logger.debug(f"Login: Base URL configured as {self.base_url}")

        payload = {
            "username": username,
            "password": password,
            "stayLoggedIn": True,
        }

        try:
            response = await self.client.post(
                login_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=payload,
            )
        except httpx.TimeoutException as e:
            logger.debug(f"Login: Timeout connecting to {login_url}")
            raise HomeboxTimeoutError(
                message=str(e),
                user_message="Connection timed out. Check if server is reachable.",
                context={"url": login_url},
            ) from e
        except httpx.ConnectError as e:
            logger.debug(f"Login: Connection failed to {login_url}: {e}")
            raise HomeboxConnectionError(
                message=str(e),
                user_message=self._classify_connection_error(e),
                context={"url": login_url},
            ) from e

        # Log response status for debugging
        logger.debug(f"Login: Response status: {response.status_code}")

        # Check content type to help diagnose HTML vs JSON issues
        content_type = response.headers.get("content-type", "")
        response_text = response.text

        # Detect common issues (without logging sensitive response body)
        if "text/html" in content_type:
            logger.warning(
                "Login: Received HTML response instead of JSON. "
                "This usually indicates a reverse proxy issue, authentication wall, "
                "or incorrect URL. Check that HBC_HOMEBOX_URL points directly to "
                "the Homebox API, not a proxy login page."
            )
        elif not response_text:
            logger.warning("Login: Received empty response body from server")

        self._ensure_success(response, "Login")

        try:
            data = response.json()
        except ValueError as json_err:
            logger.error(f"Login: Failed to parse JSON response: {json_err}")
            logger.error(f"Login: Content-Type was '{content_type}'")
            raise HomeboxAuthError(
                f"Server returned invalid JSON. Content-Type was '{content_type}'. "
                "This usually indicates a reverse proxy or server configuration issue."
            ) from json_err

        token = data.get("token") or data.get("jwt") or data.get("accessToken")
        if not token:
            logger.error(
                f"Login: Response JSON missing token field. Keys present: {list(data.keys())}"
            )
            raise HomeboxAuthError("Login response did not include a token field.")

        # Normalize token - Homebox v0.22.0+ returns with "Bearer " prefix
        # Strip it for consistent handling (we add it back in request headers)
        original_token = token
        token = _normalize_token(token)
        if token != original_token:
            logger.debug("Login: Stripped 'Bearer ' prefix from token (Homebox v0.22+ format)")
            data["token"] = token

        logger.debug("Login: Successfully obtained authentication token")
        return data

    async def refresh_token(self, token: str) -> dict[str, Any]:
        """Refresh the access token.

        Exchanges the current valid token for a new one with extended expiry.

        Args:
            token: The current bearer token.

        Returns:
            Dictionary containing token, expiresAt, and other response fields.

        Raises:
            HomeboxAuthError: If the token is expired or invalid.
            RuntimeError: If the refresh fails for other reasons.
        """
        response = await self.client.get(
            f"{self.base_url}/users/refresh",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Token refresh")

        data = response.json()

        # Normalize token - Homebox v0.22.0+ returns with "Bearer " prefix
        new_token = data.get("token", "")
        if new_token:
            original_token = new_token
            new_token = _normalize_token(new_token)
            if new_token != original_token:
                logger.debug(
                    "Token refresh: Stripped 'Bearer ' prefix from token (Homebox v0.22+ format)"
                )
                data["token"] = new_token

        logger.debug("Token refresh: Successfully obtained new token")
        return data

    async def list_locations(
        self, token: str, *, filter_children: bool | None = None
    ) -> list[dict[str, Any]]:
        """Return all available locations for the authenticated user.

        Args:
            token: The bearer token from login.
            filter_children: If True, returns only top-level locations.

        Returns:
            List of location dictionaries (raw API response).
        """
        params = {}
        if filter_children is not None:
            params["filterChildren"] = str(filter_children).lower()

        response = await self.client.get(
            f"{self.base_url}/locations",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            params=params or None,
        )
        self._ensure_success(response, "Fetch locations")
        return response.json()

    async def list_locations_typed(
        self, token: str, *, filter_children: bool | None = None
    ) -> list[Location]:
        """Return all available locations as typed Location objects.

        Args:
            token: The bearer token from login.
            filter_children: If True, returns only top-level locations.

        Returns:
            List of Location objects.
        """
        raw = await self.list_locations(token, filter_children=filter_children)
        return [Location.model_validate(loc) for loc in raw]

    async def get_location(self, token: str, location_id: str) -> dict[str, Any]:
        """Return a specific location by ID with its children.

        Args:
            token: The bearer token from login.
            location_id: The ID of the location to fetch.

        Returns:
            Location dictionary including children (raw API response).
        """
        response = await self.client.get(
            f"{self.base_url}/locations/{location_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Fetch location")
        return response.json()

    async def get_location_typed(self, token: str, location_id: str) -> Location:
        """Return a specific location by ID as a typed Location object.

        Args:
            token: The bearer token from login.
            location_id: The ID of the location to fetch.

        Returns:
            Location object including children.
        """
        raw = await self.get_location(token, location_id)
        return Location.model_validate(raw)

    async def get_location_tree(
        self, token: str, *, with_items: bool = False
    ) -> list[dict[str, Any]]:
        """Get hierarchical location tree.

        Args:
            token: The bearer token from login.
            with_items: If True, include items in the tree.

        Returns:
            List of tree item dictionaries with nested children.
        """
        params = {}
        if with_items:
            params["withItems"] = "true"

        response = await self.client.get(
            f"{self.base_url}/locations/tree",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            params=params or None,
        )
        self._ensure_success(response, "Get location tree")
        return response.json()

    @_rate_limited
    async def create_location(
        self,
        token: str,
        name: str,
        description: str = "",
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new location.

        Args:
            token: The bearer token from login.
            name: The name of the new location.
            description: Optional description for the location.
            parent_id: Optional parent location ID for nesting.

        Returns:
            The created location dictionary.
        """
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
        }
        if parent_id:
            payload["parentId"] = parent_id

        response = await self.client.post(
            f"{self.base_url}/locations",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        self._ensure_success(response, "Create location")
        return response.json()

    @_rate_limited
    async def update_location(
        self,
        token: str,
        location_id: str,
        name: str,
        description: str = "",
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing location.

        Args:
            token: The bearer token from login.
            location_id: The ID of the location to update.
            name: The new name for the location.
            description: The new description for the location.
            parent_id: The new parent location ID (or None for top-level).

        Returns:
            The updated location dictionary.
        """
        payload: dict[str, Any] = {
            "id": location_id,
            "name": name,
            "description": description,
        }
        if parent_id:
            payload["parentId"] = parent_id

        response = await self.client.put(
            f"{self.base_url}/locations/{location_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        self._ensure_success(response, "Update location")
        return response.json()

    @_rate_limited
    async def delete_location(self, token: str, location_id: str) -> None:
        """Delete a location by ID.

        Args:
            token: The bearer token from login.
            location_id: The ID of the location to delete.

        Returns:
            None
        """
        response = await self.client.delete(
            f"{self.base_url}/locations/{location_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Delete location")

    async def list_labels(self, token: str) -> list[dict[str, Any]]:
        """Return all available labels for the authenticated user.

        Args:
            token: The bearer token from login.

        Returns:
            List of label dictionaries (raw API response).
        """
        response = await self.client.get(
            f"{self.base_url}/labels",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Fetch labels")
        return response.json()

    async def list_labels_typed(self, token: str) -> list[Label]:
        """Return all available labels as typed Label objects.

        Args:
            token: The bearer token from login.

        Returns:
            List of Label objects.
        """
        raw = await self.list_labels(token)
        return [Label.model_validate(label) for label in raw]

    async def get_label(self, token: str, label_id: str) -> dict[str, Any]:
        """Return a specific label by ID.

        Args:
            token: The bearer token from login.
            label_id: The ID of the label to fetch.

        Returns:
            Label dictionary (raw API response).
        """
        response = await self.client.get(
            f"{self.base_url}/labels/{label_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Fetch label")
        return response.json()

    @_rate_limited
    async def create_label(
        self,
        token: str,
        name: str,
        description: str = "",
        color: str = "",
    ) -> dict[str, Any]:
        """Create a new label.

        Args:
            token: The bearer token from login.
            name: The name of the new label.
            description: Optional description for the label.
            color: Optional color for the label.

        Returns:
            The created label dictionary.
        """
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "color": color,
        }

        response = await self.client.post(
            f"{self.base_url}/labels",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        self._ensure_success(response, "Create label")
        return response.json()

    @_rate_limited
    async def update_label(
        self,
        token: str,
        label_id: str,
        name: str,
        description: str = "",
        color: str = "",
    ) -> dict[str, Any]:
        """Update an existing label.

        Args:
            token: The bearer token from login.
            label_id: The ID of the label to update.
            name: The new name for the label.
            description: The new description for the label.
            color: The new color for the label.

        Returns:
            The updated label dictionary.
        """
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "color": color,
        }

        response = await self.client.put(
            f"{self.base_url}/labels/{label_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        self._ensure_success(response, "Update label")
        return response.json()

    @_rate_limited
    async def delete_label(self, token: str, label_id: str) -> None:
        """Delete a label by ID.

        Args:
            token: The bearer token from login.
            label_id: The ID of the label to delete.

        Returns:
            None
        """
        response = await self.client.delete(
            f"{self.base_url}/labels/{label_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Delete label")

    @_rate_limited
    async def create_item(self, token: str, item: ItemCreate) -> dict[str, Any]:
        """Create a single item in Homebox.

        Args:
            token: The bearer token from login.
            item: The item data to create.

        Returns:
            The created item dictionary from the API (raw response).
        """
        response = await self.client.post(
            f"{self.base_url}/items",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=item.model_dump(by_alias=True, exclude_unset=True),
        )
        self._ensure_success(response, "Create item")
        return response.json()

    async def create_item_typed(self, token: str, item: ItemCreate) -> Item:
        """Create a single item in Homebox and return as typed Item object.

        Args:
            token: The bearer token from login.
            item: The item data to create.

        Returns:
            The created Item object.
        """
        raw = await self.create_item(token, item)
        return Item.model_validate(raw)

    @_rate_limited
    async def update_item(
        self, token: str, item_id: str, item_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a single item by ID.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to update.
            item_data: Dictionary of fields to update.

        Returns:
            The updated item dictionary (raw API response).
        """
        response = await self.client.put(
            f"{self.base_url}/items/{item_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=item_data,
        )
        self._ensure_success(response, "Update item")
        return response.json()

    async def update_item_typed(self, token: str, item_id: str, item_data: dict[str, Any]) -> Item:
        """Update a single item by ID and return as typed Item object.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to update.
            item_data: Dictionary of fields to update.

        Returns:
            The updated Item object.
        """
        raw = await self.update_item(token, item_id, item_data)
        return Item.model_validate(raw)

    async def list_items(
        self,
        token: str,
        *,
        location_id: str | None = None,
        label_ids: list[str] | None = None,
        query: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """List items with optional filtering, search, and pagination.

        Args:
            token: The bearer token from login.
            location_id: Optional location ID to filter items.
            label_ids: Optional list of label IDs to filter items.
            query: Optional search query string.
            page: Optional page number (1-indexed).
            page_size: Optional number of items per page.

        Returns:
            Full paginated response: {items: [...], page, pageSize, total}
        """
        params = {}
        if location_id:
            params["locations"] = location_id
        if label_ids:
            # API expects comma-separated list for array params
            params["labels"] = ",".join(label_ids)
        if query:
            params["q"] = query
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size

        response = await self.client.get(
            f"{self.base_url}/items",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            params=params or None,
        )
        self._ensure_success(response, "List items")
        # Return full pagination response: {items, page, pageSize, total}
        return response.json()

    async def search_items(
        self,
        token: str,
        *,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search items by text query with optional limit.

        This is a convenience wrapper around list_items that defaults to
        a reasonable page size for search results.

        Args:
            token: The bearer token from login.
            query: Search query string.
            limit: Maximum number of items to return (default 50).

        Returns:
            List of item dictionaries matching the search query.
        """
        response = await self.list_items(
            token,
            query=query,
            page_size=limit,
        )
        return response.get("items", [])

    async def get_item(self, token: str, item_id: str) -> dict[str, Any]:
        """Get full item details by ID.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to fetch.

        Returns:
            The item dictionary with all details (raw API response).
        """
        response = await self.client.get(
            f"{self.base_url}/items/{item_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Get item")
        return response.json()

    async def export_items(self, token: str) -> str:
        """Export all items as CSV.

        This endpoint returns all item data in a single API call, including
        fields not available in the list endpoint (serial number, manufacturer,
        model number, etc.).

        Args:
            token: The bearer token from login.

        Returns:
            CSV string with all items and their fields.
        """
        response = await self.client.get(
            f"{self.base_url}/items/export",
            headers={
                "Accept": "text/csv",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Export items")
        return response.text

    async def get_item_path(self, token: str, item_id: str) -> list[dict[str, Any]]:
        """Get the full hierarchical path of an item.

        Returns the location chain from root to the item's location.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item.

        Returns:
            List of path elements (each with id, name, type).
        """
        response = await self.client.get(
            f"{self.base_url}/items/{item_id}/path",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Get item path")
        return response.json()

    async def get_statistics(self, token: str) -> dict[str, Any]:
        """Get group statistics overview.

        Args:
            token: The bearer token from login.

        Returns:
            Statistics dict containing:
            - totalItems: Count of all items
            - totalLocations: Count of locations
            - totalLabels: Count of labels
            - totalItemPrice: Sum of item prices
            - totalWithWarranty: Count of items with warranty
            - totalUsers: Count of users
        """
        response = await self.client.get(
            f"{self.base_url}/groups/statistics",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Get statistics")
        return response.json()

    async def get_statistics_by_location(self, token: str) -> list[dict[str, Any]]:
        """Get statistics grouped by location.

        Args:
            token: The bearer token from login.

        Returns:
            List of dicts with id, name, and total (item count) for each location.
        """
        response = await self.client.get(
            f"{self.base_url}/groups/statistics/locations",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Get statistics by location")
        return response.json()

    async def get_statistics_by_label(self, token: str) -> list[dict[str, Any]]:
        """Get statistics grouped by label.

        Args:
            token: The bearer token from login.

        Returns:
            List of dicts with id, name, and total (item count) for each label.
        """
        response = await self.client.get(
            f"{self.base_url}/groups/statistics/labels",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Get statistics by label")
        return response.json()

    async def get_item_by_asset_id(self, token: str, asset_id: str) -> dict[str, Any]:
        """Get item by asset ID.

        Args:
            token: The bearer token from login.
            asset_id: The asset ID (e.g., "000-085").

        Returns:
            The first item dictionary from the paginated result.
            Note: The API returns a pagination result, we return the first item.

        Raises:
            Exception if no item found with the given asset ID.
        """
        response = await self.client.get(
            f"{self.base_url}/assets/{asset_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Get item by asset ID")
        data = response.json()
        # API returns paginated result, get first item
        items = data.get("items", [])
        if not items:
            raise ValueError(f"No item found with asset ID: {asset_id}")
        return items[0]

    async def get_item_typed(self, token: str, item_id: str) -> Item:
        """Get full item details by ID as typed Item object.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to fetch.

        Returns:
            The Item object with all details.
        """
        raw = await self.get_item(token, item_id)
        return Item.model_validate(raw)

    @_rate_limited
    async def delete_item(self, token: str, item_id: str) -> None:
        """Delete an item by ID.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to delete.

        Returns:
            None
        """
        response = await self.client.delete(
            f"{self.base_url}/items/{item_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Delete item")

    async def get_attachment(
        self,
        token: str,
        item_id: str,
        attachment_id: str,
    ) -> tuple[bytes, str]:
        """Get an attachment's content by ID.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item.
            attachment_id: The ID of the attachment.

        Returns:
            Tuple of (content_bytes, content_type).

        Raises:
            HomeboxAuthError: If authentication fails.
            FileNotFoundError: If the attachment is not found (404).
            RuntimeError: If other API errors occur.
        """
        response = await self.client.get(
            f"{self.base_url}/items/{item_id}/attachments/{attachment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Handle 404 explicitly with a specific exception type
        if response.status_code == 404:
            raise FileNotFoundError(f"Attachment {attachment_id} not found for item {item_id}")
        self._ensure_success(response, "Get attachment")
        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type

    @_rate_limited
    async def upload_attachment(
        self,
        token: str,
        item_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        attachment_type: str = "photo",
    ) -> dict[str, Any]:
        """Upload an attachment (image) to an item.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to attach to.
            file_bytes: The file content as bytes.
            filename: Name for the uploaded file.
            mime_type: MIME type of the file.
            attachment_type: Type of attachment (default: "photo").

        Returns:
            The attachment response dictionary (raw API response).
        """
        files = {"file": (filename, file_bytes, mime_type)}
        data = {"type": attachment_type, "name": filename}
        response = await self.client.post(
            f"{self.base_url}/items/{item_id}/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        self._ensure_success(response, "Upload attachment")
        return response.json()

    async def upload_attachment_typed(
        self,
        token: str,
        item_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        attachment_type: str = "photo",
    ) -> Attachment:
        """Upload an attachment (image) to an item and return typed Attachment.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to attach to.
            file_bytes: The file content as bytes.
            filename: Name for the uploaded file.
            mime_type: MIME type of the file.
            attachment_type: Type of attachment (default: "photo").

        Returns:
            The Attachment object.
        """
        raw = await self.upload_attachment(
            token, item_id, file_bytes, filename, mime_type, attachment_type
        )
        # Handle nested document structure from API
        doc = raw.get("document", {})
        return Attachment(
            id=raw.get("id", ""),
            type=raw.get("type", ""),
            document_id=doc.get("id") if doc else None,
        )

    @_rate_limited
    async def ensure_asset_ids(self, token: str) -> int:
        """Ensure all items have asset IDs assigned.

        Calls the Homebox action to assign sequential asset IDs to all items
        that don't currently have one. This is idempotent - items that already
        have asset IDs are not affected.

        Args:
            token: The bearer token from login.

        Returns:
            Number of items that were assigned asset IDs.
        """
        response = await self.client.post(
            f"{self.base_url}/actions/ensure-asset-ids",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Ensure asset IDs")
        result = response.json()
        return result.get("completed", 0)

    @staticmethod
    def _ensure_success(response: httpx.Response, context: str) -> None:
        """Raise an error if the response indicates failure."""
        # Safely get request info using public API
        request_info = ""
        try:
            if hasattr(response, "request") and response.request is not None:
                request_info = f"{response.request.method} {response.request.url.path} "
        except (AttributeError, RuntimeError):
            pass

        if response.is_success:
            logger.debug(f"{context}: {request_info}-> {response.status_code}")
            return

        # Log failed request
        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        # Raise HomeboxAuthError for 401 so callers can handle session expiry
        # Don't log 401s as errors - they're expected when session expires
        if response.status_code == 401:
            logger.debug(f"{context}: {request_info}-> 401 (unauthenticated)")
            raise HomeboxAuthError(f"{context} failed: {detail}")

        # Use domain exception for all other non-success responses
        # This allows centralized exception handling in the FastAPI layer
        logger.error(f"{context} failed: {request_info}-> {response.status_code}")
        logger.debug(f"Response detail: {detail}")
        raise HomeboxAPIError(
            message=f"{context} failed with {response.status_code}: {detail}",
            user_message=f"Homebox API error: {context} failed",
            context={"status_code": response.status_code, "detail": str(detail)[:200]},
        )
