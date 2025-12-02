"""Labels router for the Homebox Vision API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from homebox_vision import AuthenticationError
from server.dependencies import get_client, get_token

router = APIRouter(prefix="/api/labels", tags=["Labels"])


@router.get("")
async def get_labels(
    token: Annotated[str, Depends(get_token)],
) -> list[dict[str, Any]]:
    """Fetch all available labels.

    Labels can be used to categorize and filter items in Homebox.

    Args:
        token: Bearer token from login (extracted from header).

    Returns:
        List of label objects.
    """
    client = get_client()

    try:
        return await client.list_labels(token)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to fetch labels: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
