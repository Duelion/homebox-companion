"""FastAPI dependencies for dependency injection."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException

from homebox_companion import HomeboxClient

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


async def get_labels_for_context(token: str) -> list[dict[str, str]]:
    """Fetch labels and format them for AI context.

    Args:
        token: The bearer token for authentication.

    Returns:
        List of label dicts with 'id' and 'name' keys.
    """
    client = get_client()
    try:
        raw_labels = await client.list_labels(token)
        return [
            {"id": str(label.get("id", "")), "name": str(label.get("name", ""))}
            for label in raw_labels
            if label.get("id") and label.get("name")
        ]
    except Exception:
        return []
