"""FastAPI dependencies for dependency injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, UploadFile
from loguru import logger

from homebox_companion import AuthenticationError, HomeboxClient, settings
from homebox_companion.core.field_preferences import load_field_preferences

# Global client instance (set during app lifespan)
_homebox_client: HomeboxClient | None = None


def set_client(client: HomeboxClient) -> None:
    """Set the global Homebox client instance."""
    global _homebox_client
    _homebox_client = client


def get_client() -> HomeboxClient:
    """Get the shared Homebox client."""
    if _homebox_client is None:
        raise HTTPException(status_code=500, detail="Client not initialized")
    return _homebox_client


def get_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return authorization[7:]


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
    except Exception:
        # Log other errors but gracefully degrade - AI can work without labels
        logger.warning(
            "Failed to fetch labels for AI context, continuing without label suggestions",
            exc_info=True,
        )
        return []


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
) -> VisionContext:
    """FastAPI dependency that loads all vision endpoint context.

    This dependency:
    1. Extracts and validates the auth token
    2. Fetches labels for AI context
    3. Loads field preferences once (instead of 3 separate reads)

    Args:
        authorization: The Authorization header value.

    Returns:
        VisionContext with all required data for vision endpoints.
    """
    token = get_token(authorization)
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
