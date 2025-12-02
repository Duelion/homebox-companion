"""Shared FastAPI dependencies for the Homebox Vision Companion API.

This module contains dependency injection functions that are shared across
multiple routers, including authentication, client access, and label fetching.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from homebox_vision import AsyncHomeboxClient, settings

# Shared async client for connection pooling (set during lifespan)
_homebox_client: AsyncHomeboxClient | None = None


def set_homebox_client(client: AsyncHomeboxClient | None) -> None:
    """Set the shared Homebox client instance."""
    global _homebox_client
    _homebox_client = client


def get_client() -> AsyncHomeboxClient:
    """Get the shared Homebox client.

    Raises:
        HTTPException: If the client hasn't been initialized.
    """
    if _homebox_client is None:
        raise HTTPException(status_code=500, detail="Client not initialized")
    return _homebox_client


def get_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract bearer token from Authorization header.

    Args:
        authorization: The Authorization header value.

    Returns:
        The extracted bearer token.

    Raises:
        HTTPException: If the header is missing or malformed.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return authorization[7:]


async def get_labels_for_context(
    token: str,
    client: AsyncHomeboxClient | None = None,
) -> list[dict[str, str]]:
    """Fetch labels from Homebox for use as context in AI detection.

    Args:
        token: The bearer token for authentication.
        client: Optional client override; uses shared client if not provided.

    Returns:
        List of label dictionaries with 'id' and 'name' keys.
    """
    from loguru import logger

    if client is None:
        client = get_client()

    try:
        raw_labels = await client.list_labels(token)
        labels = [
            {"id": str(label.get("id", "")), "name": str(label.get("name", ""))}
            for label in raw_labels
            if label.get("id") and label.get("name")
        ]
        logger.debug(f"Loaded {len(labels)} labels for context")
        return labels
    except Exception as e:
        logger.warning(f"Failed to load labels: {e}")
        return []


def require_openai_key() -> str:
    """Ensure OpenAI API key is configured.

    Returns:
        The OpenAI API key.

    Raises:
        HTTPException: If the key is not configured.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=500,
            detail="HOMEBOX_VISION_OPENAI_API_KEY not configured",
        )
    return settings.openai_api_key
