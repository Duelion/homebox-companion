"""HTTP client wrapper for the Homebox demo environment."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import requests

from .models import DetectedItem

DEMO_BASE_URL = "https://demo.homebox.software/api/v1"

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


class HomeboxDemoClient:
    """Minimal client for the Homebox demo environment."""

    def __init__(
        self,
        base_url: str = DEMO_BASE_URL,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def login(self, username: str = "demo@example.com", password: str = "demo") -> str:
        payload = {
            "username": username,
            "password": password,
            "stayLoggedIn": True,
        }
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
        """Return all available locations for the authenticated user.

        Args:
            token: Bearer token returned from :meth:`login`.
            filter_children: When provided, forwards the ``filterChildren`` query parameter
                to filter locations that have parents.
        """

        params = None
        if filter_children is not None:
            params = {"filterChildren": str(filter_children).lower()}

        response = self.session.get(
            f"{self.base_url}/locations",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            params=params,
            timeout=20,
        )
        self._ensure_success(response, "Fetch locations")
        locations: list[dict[str, Any]] = response.json()
        return locations

    def create_items(self, token: str, items: Iterable[DetectedItem]) -> list[dict[str, Any]]:
        """Persist the provided items to the Homebox demo environment."""

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
                json=item.as_item_payload(),
                timeout=20,
            )
            self._ensure_success(response, "Create item")
            created.append(response.json())
        return created

    def update_item(self, token: str, item_id: str, item_data: dict[str, Any]) -> dict[str, Any]:
        """Update a single item by ID in the Homebox demo environment."""

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
