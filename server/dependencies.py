"""FastAPI dependencies for dependency injection."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

import httpx
from fastapi import Depends, Header, HTTPException, UploadFile
from loguru import logger

from homebox_companion import HomeboxAuthError, HomeboxClient, settings

if TYPE_CHECKING:
    from homebox_companion.chat.session import ChatSession
    from homebox_companion.chat.store import SessionStoreProtocol
    from homebox_companion.core.persistent_settings import CustomFieldDefinition
    from homebox_companion.mcp.executor import ToolExecutor

from homebox_companion.core.field_preferences import FieldPreferences, load_field_preferences


class ClientHolder:
    """Manages the lifecycle of the shared HomeboxClient instance.

    This class provides explicit lifecycle management for the HTTP client,
    making it easier to configure for testing and multi-worker deployments.

    Usage:
        # In app lifespan:
        client = HomeboxClient(base_url=settings.api_url)
        client_holder.set(client)
        yield
        await client_holder.close()

        # In tests:
        client_holder.set(mock_client)
        # ... run tests ...
        client_holder.reset()

    Note:
        In multi-worker deployments (e.g., uvicorn --workers N), each worker
        maintains its own ClientHolder instance. This is the expected behavior
        for async HTTP clients, as httpx.AsyncClient is not thread-safe.
    """

    def __init__(self) -> None:
        self._client: HomeboxClient | None = None

    def set(self, client: HomeboxClient) -> None:
        """Set the shared client instance.

        Args:
            client: The HomeboxClient instance to use.
        """
        self._client = client

    def get(self) -> HomeboxClient:
        """Get the shared client instance.

        Returns:
            The shared HomeboxClient instance.

        Raises:
            HTTPException: If the client has not been initialized.
        """
        if self._client is None:
            raise HTTPException(status_code=500, detail="Client not initialized")
        return self._client

    async def close(self) -> None:
        """Close the client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def reset(self) -> None:
        """Reset the holder without closing (for testing).

        Use this in tests to reset state between test cases.
        For normal shutdown, use close() instead.
        """
        self._client = None


# Singleton holder instance - each worker gets its own
client_holder = ClientHolder()


class SessionStoreHolder:
    """Manages the lifecycle of the shared session store.

    Similar to ClientHolder, this provides explicit lifecycle management
    for the session store, enabling testing and future backend swaps.

    Usage:
        # In app lifespan:
        session_store_holder.set(MemorySessionStore())
        yield
        # No cleanup needed for memory store

        # In tests:
        session_store_holder.set(mock_store)
        # ... run tests ...
        session_store_holder.reset()
    """

    def __init__(self) -> None:
        self._store: SessionStoreProtocol | None = None

    def set(self, store: SessionStoreProtocol) -> None:
        """Set the shared store instance.

        Args:
            store: The session store instance to use.
        """
        self._store = store

    def get(self) -> SessionStoreProtocol:
        """Get the shared store instance, creating default if needed.

        Returns:
            The shared session store instance.
        """
        if self._store is None:
            from homebox_companion.chat.store import MemorySessionStore

            self._store = MemorySessionStore()
            logger.debug("Created default MemorySessionStore")
        return self._store

    def reset(self) -> None:
        """Reset the holder (for testing).

        Use this in tests to reset state between test cases.
        """
        self._store = None


# Singleton session store holder
session_store_holder = SessionStoreHolder()


class ToolExecutorHolder:
    """Manages the shared ToolExecutor instance.

    This makes the ToolExecutor a singleton, ensuring that schema caching
    is effective across requests rather than being recreated per-request.

    The holder tracks the client reference to ensure the executor is
    recreated if the client changes (important for testing).

    Usage:
        # Get executor (auto-creates if needed):
        executor = tool_executor_holder.get(client)

        # In tests:
        tool_executor_holder.reset()
    """

    def __init__(self) -> None:
        self._executor: ToolExecutor | None = None
        self._client_id: int | None = None  # Track client identity

    def get(self, client: HomeboxClient) -> ToolExecutor:
        """Get or create the shared executor instance.

        If the client reference has changed (e.g., during testing),
        the executor is recreated with the new client.

        Args:
            client: HomeboxClient for tool execution.

        Returns:
            The shared ToolExecutor instance.
        """
        from homebox_companion.mcp.executor import ToolExecutor

        current_client_id = id(client)

        # Recreate executor if client has changed
        if self._executor is None or self._client_id != current_client_id:
            if self._executor is not None:
                logger.debug("Client changed, recreating ToolExecutor")
            self._executor = ToolExecutor(client)
            self._client_id = current_client_id
            logger.debug("Created shared ToolExecutor instance")

        return self._executor

    def reset(self) -> None:
        """Reset the holder (for testing).

        Use this in tests to reset state between test cases.
        """
        self._executor = None
        self._client_id = None


# Singleton tool executor holder
tool_executor_holder = ToolExecutorHolder()


class TokenValidator:
    """Validates tokens against Homebox with in-memory TTL cache.

    On first use of a token, calls Homebox's ``GET /users/self`` to verify it.
    Valid tokens are cached (by hash) so subsequent requests skip the check.
    Cache entries expire after ``ttl`` seconds, forcing re-validation.

    Thread-safety: Uses a lock to protect the cache dict, matching the
    pattern used by ``MemorySessionStore``.
    """

    # Default TTL: 5 minutes
    _DEFAULT_TTL = 5 * 60
    # Cleanup interval: sweep expired entries at most once per 5 minutes
    _CLEANUP_INTERVAL = 300

    def __init__(self, ttl: int | None = None) -> None:
        self._ttl = ttl or self._DEFAULT_TTL
        self._cache: dict[str, float] = {}  # token_hash -> validated_at
        self._lock = threading.Lock()
        self._last_cleanup: float = time.time()

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def _maybe_cleanup_expired(self) -> None:
        """Sweep expired entries. Caller must hold self._lock."""
        now = time.time()
        if now - self._last_cleanup < self._CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        expired = [k for k, ts in self._cache.items() if now - ts > self._ttl]
        for k in expired:
            del self._cache[k]
        if expired:
            logger.debug(f"Token cache: cleaned up {len(expired)} expired entries")

    def is_cached(self, token: str) -> bool:
        """Check if a token is in the valid cache and not expired."""
        key = self._hash(token)
        with self._lock:
            self._maybe_cleanup_expired()
            ts = self._cache.get(key)
            if ts is None:
                return False
            if time.time() - ts > self._ttl:
                del self._cache[key]
                return False
            return True

    def mark_valid(self, token: str) -> None:
        """Cache a token as validated."""
        key = self._hash(token)
        with self._lock:
            self._cache[key] = time.time()

    def reset(self) -> None:
        """Clear all cached validations."""
        with self._lock:
            self._cache.clear()


# Singleton token validator
token_validator = TokenValidator()


# =============================================================================
# CORE DEPENDENCIES (defined first so they can be used in Depends())
# =============================================================================


def get_client() -> HomeboxClient:
    """Get the shared Homebox client.

    This is a FastAPI dependency that returns the shared client instance.
    Can be overridden in tests using app.dependency_overrides[get_client].
    """
    return client_holder.get()


async def get_token(
    authorization: Annotated[str | None, Header()] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,  # type: ignore[assignment]
) -> str:
    """Extract and validate bearer token from Authorization header.

    Validates the token against Homebox on first use, then caches the
    result for subsequent requests (TTL-based expiration).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    raw_token = authorization[7:]

    # Check cache first — skip Homebox call if recently validated
    if token_validator.is_cached(raw_token):
        return raw_token

    # Validate against Homebox
    if client and await client.validate_token(raw_token):
        token_validator.mark_valid(raw_token)
        return raw_token

    raise HTTPException(status_code=401, detail="Invalid or expired token")


# =============================================================================
# COMPOSITE DEPENDENCIES (depend on core dependencies above)
# =============================================================================


def get_executor(
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> ToolExecutor:
    """Get the shared ToolExecutor.

    This is a FastAPI dependency that returns the shared executor instance.
    Can be overridden in tests using app.dependency_overrides[get_executor].
    """
    return tool_executor_holder.get(client)


def get_session(
    token: Annotated[str, Depends(get_token)],
) -> ChatSession:
    """Get the chat session for the current user.

    This is a FastAPI dependency that retrieves (or creates) the session
    for the authenticated user.

    Args:
        token: The user's auth token (from get_token dependency).

    Returns:
        The ChatSession for this user.
    """
    store = session_store_holder.get()
    return store.get(token)


def require_auth(token: Annotated[str, Depends(get_token)]) -> None:
    """Dependency that validates authentication without returning the token.

    Use this when a route needs authentication but doesn't use the token directly.
    This avoids injecting unused dependencies and makes intent clear.

    Usage:
        @router.get("/protected", dependencies=[Depends(require_auth)])
        async def protected_route() -> dict:
            return {"status": "authenticated"}
    """
    # Token validation happens in get_token; explicitly acknowledge unused param
    _ = token


def require_llm_configured() -> str:
    """
    FastAPI dependency to ensure LLM is configured.

    Use this as a FastAPI dependency in endpoints that require LLM access.
    The returned key can be used directly or ignored if only validation is needed.

    Resolution order (same as LLM Router):
    1. PRIMARY profile from settings.yaml (configured via Settings UI)
    2. Environment variables (HBC_LLM_API_KEY or HBC_OPENAI_API_KEY)

    Returns:
        The configured LLM API key.

    Raises:
        HTTPException: 500 if LLM API key is not configured.
    """
    from homebox_companion.core.llm_utils import resolve_llm_credentials

    creds = resolve_llm_credentials()
    if not creds.api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Configure a profile in Settings or set HBC_LLM_API_KEY.",
        )
    return creds.api_key


async def validate_file_size(file: UploadFile) -> bytes:
    """Read and validate file size against configured limit.

    Args:
        file: The uploaded file to validate.

    Returns:
        The file contents as bytes.

    Raises:
        HTTPException: If file exceeds size limit or is empty.
    """
    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    max_size = settings.max_upload_size_bytes
    if len(contents) > max_size:
        max_mb = settings.max_upload_size_mb
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_mb}MB",
        )

    return contents


async def validate_files_size(files: list[UploadFile]) -> list[tuple[bytes, str]]:
    """Read and validate multiple files against configured limit.

    Args:
        files: List of uploaded files to validate.

    Returns:
        List of tuples containing (file_bytes, content_type).

    Raises:
        HTTPException: If any file exceeds size limit or is empty.
    """
    results = []
    for file in files:
        contents = await validate_file_size(file)
        content_type = file.content_type or "application/octet-stream"
        results.append((contents, content_type))
    return results


async def get_tags_for_context(token: str) -> list[dict[str, str]]:
    """Fetch tags and format them for AI context.

    Args:
        token: The bearer token for authentication.

    Returns:
        List of tag dicts with 'id' and 'name' keys.

    Raises:
        HomeboxAuthError: If authentication fails (re-raised to caller).
        RuntimeError: If the API returns an unexpected error (not transient).
    """
    client = get_client()
    try:
        raw_tags = await client.list_tags(token)
        return [
            {"id": str(tag.get("id", "")), "name": str(tag.get("name", ""))}
            for tag in raw_tags
            if tag.get("id") and tag.get("name")
        ]
    except HomeboxAuthError:
        # Re-raise auth errors - session is invalid and caller needs to know
        logger.warning("Authentication failed while fetching tags for AI context")
        raise
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        # Transient network errors: gracefully degrade - AI can work without tags
        logger.warning(
            f"Transient network error fetching tags for AI context: {type(e).__name__}. "
            "Continuing without tag suggestions.",
        )
        return []
    # Let other errors (RuntimeError from API, schema errors, etc.) propagate
    # to surface issues rather than silently degrading AI behavior


async def get_valid_tag_ids(token: str, client: HomeboxClient) -> set[str]:
    """Fetch valid tag IDs from Homebox as a set for O(1) validation.

    Used to filter out invalid/stale tag IDs before creating items.

    Args:
        token: The bearer token for authentication.
        client: The HomeboxClient instance.

    Returns:
        Set of valid tag ID strings, or empty set on failure.
    """
    try:
        raw_tags = await client.list_tags(token)
        return {str(tag.get("id")) for tag in raw_tags if tag.get("id")}
    except HomeboxAuthError:
        # Re-raise auth errors - caller needs to handle
        raise
    except Exception as e:
        # Non-fatal: log and return empty set - items will be created without tags
        logger.warning(f"Failed to fetch tags for validation: {e}")
        return set()


# =============================================================================
# VISION CONTEXT - Bundles all context needed for vision endpoints
# =============================================================================


@dataclass
class VisionContext:
    """Context bundle for vision AI endpoints.

    This dataclass consolidates all the common context needed by vision
    endpoints, reducing boilerplate and ensuring field preferences are
    only loaded once per request.

    Attributes:
        token: Bearer token for Homebox API authentication.
        tags: List of available tags for AI context.
        field_preferences: Custom field instructions dict, or None if no customizations.
        output_language: Configured output language, or None for default (English).
        default_tag_id: ID of tag to auto-add, or None.
        custom_fields: User-defined custom field definitions for AI detection.
    """

    token: str
    tags: list[dict[str, str]]
    field_preferences: dict[str, str] | None
    output_language: str | None
    default_tag_id: str | None
    custom_fields: list[CustomFieldDefinition]


async def get_vision_context(
    authorization: Annotated[str | None, Header()] = None,
    x_field_preferences: Annotated[str | None, Header()] = None,
) -> VisionContext:
    """FastAPI dependency that loads all vision endpoint context.

    This dependency:
    1. Extracts and validates the auth token
    2. Fetches tags for AI context
    3. Loads field preferences (from header in demo mode, or from file/env)

    Args:
        authorization: The Authorization header value.
        x_field_preferences: Optional JSON-encoded field preferences (for demo mode).

    Returns:
        VisionContext with all required data for vision endpoints.
    """
    token = get_token(authorization)

    # Load field preferences from header if provided (demo mode), otherwise from file
    if x_field_preferences:
        logger.debug("Using field preferences from X-Field-Preferences header (demo mode)")
        try:
            prefs_dict = json.loads(x_field_preferences)
            # Filter out None values - let model defaults fill in missing fields
            filtered = {k: v for k, v in prefs_dict.items() if v is not None}
            prefs = FieldPreferences.model_validate(filtered)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid field preferences in header, ignoring: {e}")
            prefs = load_field_preferences()
    else:
        prefs = load_field_preferences()

    # Determine output language (None means use default English)
    output_language = None if prefs.output_language.lower() == "english" else prefs.output_language

    # Load custom field definitions from persistent settings
    from homebox_companion.core.persistent_settings import get_settings

    persistent = get_settings()

    return VisionContext(
        token=token,
        tags=await get_tags_for_context(token),
        # get_effective_customizations returns all prompt fields
        field_preferences=prefs.get_effective_customizations(),
        output_language=output_language,
        default_tag_id=prefs.default_tag_id,
        custom_fields=persistent.custom_fields,
    )
