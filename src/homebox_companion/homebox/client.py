"""Async HTTP client for the Homebox API using HTTPX.

This module provides an async client for interacting with the Homebox REST API.
The sync client has been removed - use async/await throughout.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..core.config import settings
from ..core.exceptions import AuthenticationError
from .models import ItemCreate

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


class HomeboxClient:
    """Async client for the Homebox API using HTTPX AsyncClient.

    This client provides connection pooling and session management
    for asynchronous interaction with a Homebox instance.

    Args:
        base_url: The base URL of the Homebox API. Defaults to the configured API URL.
        client: Optional pre-configured HTTPX AsyncClient to use.

    Example:
        >>> async with HomeboxClient() as client:
        ...     token = await client.login("user@example.com", "password")
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

    async def login(self, username: str, password: str) -> str:
        """Authenticate with Homebox and return the bearer token.

        Args:
            username: The user's email address.
            password: The user's password.

        Returns:
            The bearer token for subsequent API calls.

        Raises:
            AuthenticationError: If authentication fails.
        """
        payload = {
            "username": username,
            "password": password,
            "stayLoggedIn": True,
        }
        response = await self.client.post(
            f"{self.base_url}/users/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
        )
        self._ensure_success(response, "Login")
        data = response.json()
        token = data.get("token") or data.get("jwt") or data.get("accessToken")
        if not token:
            raise AuthenticationError("Login response did not include a token field.")
        return token

    async def list_locations(
        self, token: str, *, filter_children: bool | None = None
    ) -> list[dict[str, Any]]:
        """Return all available locations for the authenticated user.

        Args:
            token: The bearer token from login.
            filter_children: If True, returns only top-level locations.

        Returns:
            List of location dictionaries.
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

    async def get_location(self, token: str, location_id: str) -> dict[str, Any]:
        """Return a specific location by ID with its children.

        Args:
            token: The bearer token from login.
            location_id: The ID of the location to fetch.

        Returns:
            Location dictionary including children.
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

    async def list_labels(self, token: str) -> list[dict[str, Any]]:
        """Return all available labels for the authenticated user.

        Args:
            token: The bearer token from login.

        Returns:
            List of label dictionaries.
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

    async def create_item(self, token: str, item: ItemCreate) -> dict[str, Any]:
        """Create a single item in Homebox.

        Args:
            token: The bearer token from login.
            item: The item data to create.

        Returns:
            The created item dictionary from the API.
        """
        response = await self.client.post(
            f"{self.base_url}/items",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=item.to_payload(),
        )
        self._ensure_success(response, "Create item")
        return response.json()

    async def update_item(
        self, token: str, item_id: str, item_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a single item by ID.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to update.
            item_data: Dictionary of fields to update.

        Returns:
            The updated item dictionary.
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

    async def get_item(self, token: str, item_id: str) -> dict[str, Any]:
        """Get full item details by ID.

        Args:
            token: The bearer token from login.
            item_id: The ID of the item to fetch.

        Returns:
            The item dictionary with all details.
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
            The attachment response dictionary.
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

    @staticmethod
    def _ensure_success(response: httpx.Response, context: str) -> None:
        """Raise an error if the response indicates failure."""
        if response.is_success:
            return
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        # Raise AuthenticationError for 401 so callers can handle session expiry
        if response.status_code == 401:
            raise AuthenticationError(f"{context} failed: {detail}")
        raise RuntimeError(f"{context} failed with {response.status_code}: {detail}")




