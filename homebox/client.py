"""HTTP client wrapper for the Homebox demo environment using HTTPX."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import httpx

from .models import DetectedItem

DEMO_BASE_URL = "https://demo.homebox.software/api/v1"

# Default timeout configuration
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Reuse the browser-style headers to avoid being blocked by network protections.
DEFAULT_HEADERS: dict[str, str] = {
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


class HomeboxClient:
    """Synchronous client for the Homebox API using HTTPX."""

    def __init__(
        self,
        base_url: str = DEMO_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> HomeboxClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def login(self, username: str = "demo@example.com", password: str = "demo") -> str:
        """Authenticate and return the bearer token."""
        payload = {
            "username": username,
            "password": password,
            "stayLoggedIn": True,
        }
        response = self.client.post(
            f"{self.base_url}/users/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
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
        """Return all available locations for the authenticated user."""
        params = {}
        if filter_children is not None:
            params["filterChildren"] = str(filter_children).lower()

        response = self.client.get(
            f"{self.base_url}/locations",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            params=params or None,
        )
        self._ensure_success(response, "Fetch locations")
        return response.json()

    def list_labels(self, token: str) -> list[dict[str, Any]]:
        """Return all available labels for the authenticated user."""
        response = self.client.get(
            f"{self.base_url}/labels",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Fetch labels")
        return response.json()

    def create_item(self, token: str, item: DetectedItem) -> dict[str, Any]:
        """Create a single item in Homebox."""
        response = self.client.post(
            f"{self.base_url}/items",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=item.as_item_payload(),
        )
        self._ensure_success(response, "Create item")
        return response.json()

    def create_items(self, token: str, items: Iterable[DetectedItem]) -> list[dict[str, Any]]:
        """Create multiple items in Homebox."""
        created: list[dict[str, Any]] = []
        for item in items:
            created.append(self.create_item(token, item))
        return created

    def update_item(self, token: str, item_id: str, item_data: dict[str, Any]) -> dict[str, Any]:
        """Update a single item by ID."""
        response = self.client.put(
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

    @staticmethod
    def _ensure_success(response: httpx.Response, context: str) -> None:
        """Raise an error if the response indicates failure."""
        if response.is_success:
            return
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise RuntimeError(f"{context} failed with {response.status_code}: {detail}")


class AsyncHomeboxClient:
    """Async client for the Homebox API using HTTPX AsyncClient."""

    def __init__(
        self,
        base_url: str = DEMO_BASE_URL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
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

    async def __aenter__(self) -> AsyncHomeboxClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def login(self, username: str = "demo@example.com", password: str = "demo") -> str:
        """Authenticate and return the bearer token."""
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
            raise RuntimeError("Login response did not include a token field.")
        return token

    async def list_locations(
        self, token: str, *, filter_children: bool | None = None
    ) -> list[dict[str, Any]]:
        """Return all available locations for the authenticated user."""
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
        """Return a specific location by ID with its children."""
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
        """Return all available labels for the authenticated user."""
        response = await self.client.get(
            f"{self.base_url}/labels",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Fetch labels")
        return response.json()

    async def create_item(self, token: str, item: DetectedItem) -> dict[str, Any]:
        """Create a single item in Homebox."""
        response = await self.client.post(
            f"{self.base_url}/items",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=item.as_item_payload(),
        )
        self._ensure_success(response, "Create item")
        return response.json()

    async def create_items(self, token: str, items: Iterable[DetectedItem]) -> list[dict[str, Any]]:
        """Create multiple items in Homebox."""
        created: list[dict[str, Any]] = []
        for item in items:
            created.append(await self.create_item(token, item))
        return created

    async def update_item(
        self, token: str, item_id: str, item_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update a single item by ID."""
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

    async def upload_attachment(
        self,
        token: str,
        item_id: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str = "image/jpeg",
        attachment_type: str = "photo",
    ) -> dict[str, Any]:
        """Upload an attachment (image) to an item."""
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

    async def get_item(self, token: str, item_id: str) -> dict[str, Any]:
        """Get full item details by ID."""
        response = await self.client.get(
            f"{self.base_url}/items/{item_id}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        self._ensure_success(response, "Get item")
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
        raise RuntimeError(f"{context} failed with {response.status_code}: {detail}")


# Backwards compatibility alias
HomeboxDemoClient = HomeboxClient
