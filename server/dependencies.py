"""FastAPI dependencies for dependency injection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Header, HTTPException, UploadFile
from loguru import logger

from homebox_companion import AuthenticationError, HomeboxClient, settings
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

    @property
    def is_initialized(self) -> bool:
        """Check if the client has been initialized."""
        return self._client is not None


# Singleton holder instance - each worker gets its own
client_holder = ClientHolder()


def set_client(client: HomeboxClient) -> None:
    """Set the global Homebox client instance.

    This is a convenience wrapper for backward compatibility.
    Prefer using client_holder.set() directly for clarity.
    """
    client_holder.set(client)


def get_client() -> HomeboxClient:
    """Get the shared Homebox client.

    This is a FastAPI dependency that returns the shared client instance.
    Can be overridden in tests using app.dependency_overrides[get_client].
    """
    return client_holder.get()


def get_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return authorization[7:]


def require_llm_configured() -> str:
    """Dependency that ensures LLM API key is configured.

    Use this as a FastAPI dependency in endpoints that require LLM access.
    The returned key can be used directly or ignored if only validation is needed.

    Returns:
        The configured LLM API key.

    Raises:
        HTTPException: 500 if LLM API key is not configured.
    """
    if not settings.effective_llm_api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Set HBC_LLM_API_KEY or HBC_OPENAI_API_KEY.",
        )
    return settings.effective_llm_api_key


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


async def get_labels_for_context(token: str) -> list[dict[str, str]]:
    """Fetch labels and format them for AI context.

    Args:
        token: The bearer token for authentication.

    Returns:
        List of label dicts with 'id' and 'name' keys.

    Raises:
        AuthenticationError: If authentication fails (re-raised to caller).
        RuntimeError: If the API returns an unexpected error (not transient).
    """
    client = get_client()
    try:
        raw_labels = await client.list_labels(token)
        return [
            {"id": str(label.get("id", "")), "name": str(label.get("name", ""))}
            for label in raw_labels
            if label.get("id") and label.get("name")
        ]
    except AuthenticationError:
        # Re-raise auth errors - session is invalid and caller needs to know
        logger.warning("Authentication failed while fetching labels for AI context")
        raise
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        # Transient network errors: gracefully degrade - AI can work without labels
        logger.warning(
            f"Transient network error fetching labels for AI context: {type(e).__name__}. "
            "Continuing without label suggestions.",
        )
        return []
    # Let other errors (RuntimeError from API, schema errors, etc.) propagate
    # to surface issues rather than silently degrading AI behavior


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
        labels: List of available labels for AI context.
        field_preferences: Custom field instructions dict, or None if no customizations.
        output_language: Configured output language, or None for default (English).
        default_label_id: ID of label to auto-add, or None.
    """

    token: str
    labels: list[dict[str, str]]
    field_preferences: dict[str, str] | None
    output_language: str | None
    default_label_id: str | None


async def get_vision_context(
    authorization: Annotated[str | None, Header()] = None,
    x_field_preferences: Annotated[str | None, Header()] = None,
) -> VisionContext:
    """FastAPI dependency that loads all vision endpoint context.

    This dependency:
    1. Extracts and validates the auth token
    2. Fetches labels for AI context
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
            prefs = FieldPreferences.model_validate(prefs_dict)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid field preferences in header, ignoring: {e}")
            prefs = load_field_preferences()
    else:
        prefs = load_field_preferences()

    # Determine output language (None means use default English)
    lang = prefs.get_output_language()
    output_language = None if lang.lower() == "english" else lang

    return VisionContext(
        token=token,
        labels=await get_labels_for_context(token),
        # Always pass effective customizations (user values merged with defaults)
        # This ensures prompt builders don't need their own fallback defaults
        field_preferences=prefs.get_effective_customizations(),
        output_language=output_language,
        default_label_id=prefs.default_label_id,
    )
