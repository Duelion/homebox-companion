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
from .models import Attachment, Group, Item, ItemCreate, Location, Tag


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
        store=store.MemoryStore(),
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

    All /v1/items/* and /v1/locations/* endpoints have been replaced
    with /v1/entities/* as of Homebox 0.26 (Entity Merge).

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
        *,
        extra_headers_factory: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self.base_url = (base_url or settings.api_url).rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
        self._entity_types_cache: dict[str | None, list[dict[str, Any]]] = {}
        self._extra_headers_factory = extra_headers_factory

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
        if "getaddrinfo failed" in error_str or isinstance(getattr(e, "__cause__", None), socket.gaierror):
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
        return "Cannot connect to Homebox server. Please check your network and server configuration."

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
            logger.error(f"Login: Response JSON missing token field. Keys present: {list(data.keys())}")
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
        # NOTE: Intentionally uses inline headers instead of _auth_headers()
        # because /users/* endpoints are not group-scoped and must not
        # receive the X-Tenant header.
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
                logger.debug("Token refresh: Stripped 'Bearer ' prefix from token (Homebox v0.22+ format)")
                data["token"] = new_token

        logger.debug("Token refresh: Successfully obtained new token")
        return data

    async def logout(self, token: str) -> None:
        """Invalidate the current session by calling Homebox's logout endpoint.

        This tells the Homebox server to revoke the token, preventing further use.

        Args:
            token: The bearer token to invalidate.

        Raises:
            HomeboxAuthError: If the token is already invalid.
        """
        # NOTE: Inline headers — /users/* is not group-scoped (see refresh_token).
        try:
            response = await self.client.post(
                f"{self.base_url}/users/logout",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            self._ensure_success(response, "Logout")
            logger.info("Logout: Token invalidated successfully")
        except Exception:
            # Best-effort: even if server-side logout fails, we still
            # clear local state. Log but don't propagate.
            logger.warning("Logout: Failed to invalidate token on Homebox server")

    async def validate_token(self, token: str) -> bool:
        """Validate a token by calling Homebox's user self endpoint.

        This is a lightweight check that verifies the token is accepted
        by the Homebox server. Used by the companion app to reject
        invalid/expired tokens before processing local-only endpoints.

        Args:
            token: The bearer token to validate.

        Returns:
            True if token is valid, False otherwise.
        """
        # NOTE: Inline headers — /users/* is not group-scoped (see refresh_token).
        try:
            response = await self.client.get(
                f"{self.base_url}/users/self",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            return response.status_code == 200
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
            # If we can't reach Homebox, we can't validate — reject the token
            logger.warning("Token validation failed: cannot reach Homebox server")
            return False

    def _auth_headers(
        self, token: str, *, group_id: str | None = None, content_type: str | None = None,
    ) -> dict[str, str]:
        """Build standard auth headers, optionally scoping to a specific group.

        Group resolution priority:
        1. Explicit ``group_id`` kwarg (direct usage, tests)
        2. ``extra_headers_factory`` (server middleware via ContextVar)
        3. None (no scoping, use default group)

        Args:
            token: The bearer token.
            group_id: Optional group UUID to scope the request via X-Tenant header.
                Takes precedence over the factory for tests and CLI use.
            content_type: Optional Content-Type header value.

        Returns:
            Headers dict ready for use in requests.
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }
        # Explicit kwarg takes precedence (for tests, CLI, direct usage)
        if group_id:
            headers["X-Tenant"] = group_id
        elif self._extra_headers_factory:
            headers.update(self._extra_headers_factory())
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _raw_auth_headers(
        self, token: str, *, accept: str | None = None,
    ) -> dict[str, str]:
        """Build auth headers without the default Accept: application/json.

        Used by methods that need non-standard Accept headers (e.g. binary
        downloads, text/plain responses) or multipart uploads where httpx
        sets Content-Type automatically.

        Args:
            token: The bearer token.
            accept: Optional Accept header value. Omitted if None.

        Returns:
            Headers dict with auth + factory headers.
        """
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
        if accept:
            headers["Accept"] = accept
        if self._extra_headers_factory:
            headers.update(self._extra_headers_factory())
        return headers

    async def list_groups(self, token: str) -> list[dict[str, Any]]:
        """Return all groups (collections) the authenticated user belongs to.

        Args:
            token: The bearer token from login.

        Returns:
            List of group dictionaries with id, name, currency, etc.
        """
        response = await self.client.get(
            f"{self.base_url}/groups/all",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "List groups")
        return response.json()

    async def list_groups_typed(self, token: str) -> list[Group]:
        """Return all groups as typed Group objects.

        Args:
            token: The bearer token from login.

        Returns:
            List of Group objects.
        """
        raw = await self.list_groups(token)
        return [Group.model_validate(g) for g in raw]

    async def list_entity_types(self, token: str) -> list[dict[str, Any]]:
        """Return all available entity types for the authenticated group.

        Args:
            token: The bearer token from login.

        Returns:
            List of entity type dicts (each has id, name, isLocation).
        """
        response = await self.client.get(
            f"{self.base_url}/entity-types",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "List entity types")
        return response.json()

    def _effective_group_id(self) -> str | None:
        """Return the current group ID from the factory, or None."""
        if self._extra_headers_factory:
            headers = self._extra_headers_factory()
            return headers.get("X-Tenant")
        return None

    async def _resolve_entity_type_id(self, token: str, *, is_location: bool) -> str:
        """Resolve the entity type UUID for 'Item' or 'Location'.

        Fetches entity types from the API on first call per group, then
        caches the result keyed by the effective group ID.  Switching
        collections automatically gets a fresh lookup.

        Args:
            token: The bearer token from login.
            is_location: If True, resolve the location type; otherwise item type.

        Returns:
            The UUID string for the matching entity type.

        Raises:
            ValueError: If no matching entity type is found.
        """
        # Cache keyed by effective group ID so a collection switch
        # doesn't reuse stale entity-type UUIDs from another group.
        gid = self._effective_group_id()
        if gid not in self._entity_types_cache:
            self._entity_types_cache[gid] = await self.list_entity_types(token)

        for et in self._entity_types_cache[gid]:
            if et.get("isLocation") == is_location:
                return et["id"]

        kind = "location" if is_location else "item"
        msg = f"No {kind} entity type found on this Homebox instance"
        raise ValueError(msg)

    async def list_locations(
        self, token: str, *, filter_children: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Return all available locations for the authenticated user.

        Args:
            token: The bearer token from login.
            filter_children: If True, returns only top-level locations.

        Returns:
            List of location dictionaries (raw API response).
        """
        params: dict[str, str] = {"isLocation": "true"}
        if filter_children is not None:
            params["filterChildren"] = str(filter_children).lower()

        response = await self.client.get(
            f"{self.base_url}/entities",
            headers=self._auth_headers(token),
            params=params,
        )
        self._ensure_success(response, "Fetch locations")
        # 0.26 returns paginated {items: [...], page, pageSize, total}
        data = response.json()
        return data.get("items", data) if isinstance(data, dict) else data

    async def list_locations_typed(
        self, token: str, *, filter_children: bool | None = None,
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

        In Homebox 0.26+, ``GET /entities/{id}`` no longer returns a nested
        ``children`` array.  We synthesise it by issuing a second request
        filtered to ``parentIds={id}&isLocation=true``.

        Args:
            token: The bearer token from login.
            location_id: The ID of the location to fetch.

        Returns:
            Location dictionary with a synthesised ``children`` list.
        """
        headers = self._auth_headers(token)

        response = await self.client.get(
            f"{self.base_url}/entities/{location_id}",
            headers=headers,
        )
        self._ensure_success(response, "Fetch location")
        location = response.json()

        # If children are already present (future API change), skip extra call
        if "children" not in location:
            children_resp = await self.client.get(
                f"{self.base_url}/entities",
                headers=headers,
                params={"parentIds": location_id, "isLocation": "true"},
            )
            self._ensure_success(children_resp, "Fetch location children")
            children_data = children_resp.json()
            children_items = (
                children_data.get("items", children_data) if isinstance(children_data, dict) else children_data
            )
            location["children"] = children_items

        return location

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
        self, token: str, *, with_items: bool = False,
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
            f"{self.base_url}/entities/tree",
            headers=self._auth_headers(token),
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
        entity_type_id = await self._resolve_entity_type_id(token, is_location=True)
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "entityTypeId": entity_type_id,
        }
        if parent_id:
            payload["parentId"] = parent_id

        response = await self.client.post(
            f"{self.base_url}/entities",
            headers=self._auth_headers(token, content_type="application/json"),
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
            f"{self.base_url}/entities/{location_id}",
            headers=self._auth_headers(token, content_type="application/json"),
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
            f"{self.base_url}/entities/{location_id}",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "Delete location")

    async def list_tags(self, token: str) -> list[dict[str, Any]]:
        """Return all available tags for the authenticated user.

        Args:
            token: The bearer token from login.

        Returns:
            List of tag dictionaries (raw API response).
        """
        response = await self.client.get(
            f"{self.base_url}/tags",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "Fetch tags")
        return response.json()

    async def list_tags_typed(self, token: str) -> list[Tag]:
        """Return all available tags as typed Tag objects.

        Args:
            token: The bearer token from login.

        Returns:
            List of Tag objects.
        """
        raw = await self.list_tags(token)
        return [Tag.model_validate(tag) for tag in raw]

    async def get_tag(self, token: str, tag_id: str) -> dict[str, Any]:
        """Return a specific tag by ID.

        Args:
            token: The bearer token from login.
            tag_id: The ID of the tag to fetch.

        Returns:
            Tag dictionary (raw API response).
        """
        response = await self.client.get(
            f"{self.base_url}/tags/{tag_id}",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "Fetch tag")
        return response.json()

    @_rate_limited
    async def create_tag(
        self,
        token: str,
        name: str,
        description: str = "",
        color: str = "",
    ) -> dict[str, Any]:
        """Create a new tag.

        Args:
            token: The bearer token from login.
            name: The name of the new tag.
            description: Optional description for the tag.
            color: Optional color for the tag.

        Returns:
            The created tag dictionary.
        """
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "color": color,
        }

        response = await self.client.post(
            f"{self.base_url}/tags",
            headers=self._auth_headers(token, content_type="application/json"),
            json=payload,
        )
        self._ensure_success(response, "Create tag")
        return response.json()

    @_rate_limited
    async def update_tag(
        self,
        token: str,
        tag_id: str,
        name: str,
        description: str = "",
        color: str = "",
    ) -> dict[str, Any]:
        """Update an existing tag.

        Args:
            token: The bearer token from login.
            tag_id: The ID of the tag to update.
            name: The new name for the tag.
            description: The new description for the tag.
            color: The new color for the tag.

        Returns:
            The updated tag dictionary.
        """
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "color": color,
        }

        response = await self.client.put(
            f"{self.base_url}/tags/{tag_id}",
            headers=self._auth_headers(token, content_type="application/json"),
            json=payload,
        )
        self._ensure_success(response, "Update tag")
        return response.json()

    @_rate_limited
    async def delete_tag(self, token: str, tag_id: str) -> None:
        """Delete a tag by ID.

        Args:
            token: The bearer token from login.
            tag_id: The ID of the tag to delete.

        Returns:
            None
        """
        response = await self.client.delete(
            f"{self.base_url}/tags/{tag_id}",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "Delete tag")

    @_rate_limited
    async def create_item(
        self, token: str, item: ItemCreate,
    ) -> dict[str, Any]:
        """Create a single item in Homebox.

        Args:
            token: The bearer token from login.
            item: The item data to create.

        Returns:
            The created item dictionary from the API (raw response).
        """
        payload = item.model_dump(by_alias=True, exclude_unset=True)
        # Inject entityTypeId (resolved from the instance's entity type cache)
        payload["entityTypeId"] = await self._resolve_entity_type_id(token, is_location=False)

        response = await self.client.post(
            f"{self.base_url}/entities",
            headers=self._auth_headers(token, content_type="application/json"),
            json=payload,
        )
        self._ensure_success(response, "Create item")
        return response.json()

    async def create_item_typed(
        self, token: str, item: ItemCreate,
    ) -> Item:
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
        self, token: str, item_id: str, item_data: dict[str, Any],
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
            f"{self.base_url}/entities/{item_id}",
            headers=self._auth_headers(token, content_type="application/json"),
            json=item_data,
        )
        self._ensure_success(response, "Update item")
        return response.json()

    async def update_item_typed(
        self, token: str, item_id: str, item_data: dict[str, Any],
    ) -> Item:
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
        tag_ids: list[str] | None = None,
        query: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        """List items with optional filtering, search, and pagination.

        Args:
            token: The bearer token from login.
            location_id: Optional location ID to filter items.
            tag_ids: Optional list of tag IDs to filter items.
            query: Optional search query string.
            page: Optional page number (1-indexed).
            page_size: Optional number of items per page.

        Returns:
            Full paginated response: {items: [...], page, pageSize, total}
        """
        params = {}
        if location_id:
            params["parentIds"] = location_id
        if tag_ids:
            # API expects comma-separated list for array params
            params["tags"] = ",".join(tag_ids)
        if query:
            params["q"] = query
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size

        response = await self.client.get(
            f"{self.base_url}/entities",
            headers=self._auth_headers(token),
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
            f"{self.base_url}/entities/{item_id}",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "Get item")
        return response.json()

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
            f"{self.base_url}/entities/{item_id}/path",
            headers=self._auth_headers(token),
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
            - totalTags: Count of tags
            - totalItemPrice: Sum of item prices
            - totalWithWarranty: Count of items with warranty
            - totalUsers: Count of users
        """
        response = await self.client.get(
            f"{self.base_url}/groups/statistics",
            headers=self._auth_headers(token),
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
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "Get statistics by location")
        return response.json()

    async def get_statistics_by_tag(self, token: str) -> list[dict[str, Any]]:
        """Get statistics grouped by tag.

        Args:
            token: The bearer token from login.

        Returns:
            List of dicts with id, name, and total (item count) for each tag.
        """
        response = await self.client.get(
            f"{self.base_url}/groups/statistics/tags",
            headers=self._auth_headers(token),
        )
        self._ensure_success(response, "Get statistics by tag")
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
            headers=self._auth_headers(token),
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
            f"{self.base_url}/entities/{item_id}",
            headers=self._auth_headers(token),
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
            f"{self.base_url}/entities/{item_id}/attachments/{attachment_id}",
            headers=self._raw_auth_headers(token),
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
            f"{self.base_url}/entities/{item_id}/attachments",
            headers=self._raw_auth_headers(token),
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
        raw = await self.upload_attachment(token, item_id, file_bytes, filename, mime_type, attachment_type)
        # Handle nested document structure from API
        doc = raw.get("document", {})
        return Attachment(
            id=raw.get("id", ""),
            type=raw.get("type", ""),
            document_id=doc.get("id") if doc else None,  # ty: ignore[unknown-argument]
        )

    @_rate_limited
    async def print_label(self, token: str, item_id: str) -> str:
        """Trigger server-side label printing for an item.

        Calls the undocumented Homebox labelmaker endpoint with ?print=true
        to execute the configured HBOX_LABEL_MAKER_PRINT_COMMAND on the server.

        Args:
            token: The bearer token from login.
            item_id: The UUID of the item to print a label for.

        Returns:
            The text response from Homebox (typically "Printed!").

        Raises:
            HomeboxAPIError: If the labelmaker endpoint is not available or
                the print command is not configured on the Homebox server.
        """
        response = await self.client.get(
            f"{self.base_url}/labelmaker/item/{item_id}",
            params={"print": "true"},
            headers=self._raw_auth_headers(token, accept="text/plain"),
        )
        self._ensure_success(response, "Print label")
        return response.text

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
            headers=self._auth_headers(token),
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
