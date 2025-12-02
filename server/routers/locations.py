"""Locations router for the Homebox Vision API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from homebox_vision import AuthenticationError
from server.dependencies import get_client, get_token

router = APIRouter(prefix="/api/locations", tags=["Locations"])


@router.get("")
async def get_locations(
    token: Annotated[str, Depends(get_token)],
    filter_children: bool | None = None,
) -> list[dict[str, Any]]:
    """Fetch all available locations.

    Args:
        token: Bearer token from login (extracted from header).
        filter_children: If true, returns only top-level locations (no children).

    Returns:
        List of location objects.
    """
    client = get_client()

    try:
        return await client.list_locations(token, filter_children=filter_children)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to fetch locations: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tree")
async def get_locations_tree(
    token: Annotated[str, Depends(get_token)],
) -> list[dict[str, Any]]:
    """Fetch top-level locations with children info for hierarchical navigation.

    Returns locations with their children embedded for building a tree UI.
    This is more efficient than making separate calls for each location.

    Args:
        token: Bearer token from login (extracted from header).

    Returns:
        List of top-level locations with embedded children.
    """
    client = get_client()

    try:
        # Get only top-level locations (those without parents)
        top_level = await client.list_locations(token, filter_children=True)

        # Fetch details for each to get children info
        enriched = []
        for loc in top_level:
            try:
                details = await client.get_location(token, loc["id"])
                enriched.append({
                    "id": details.get("id"),
                    "name": details.get("name"),
                    "description": details.get("description", ""),
                    "itemCount": loc.get("itemCount", 0),
                    "children": details.get("children", []),
                })
            except Exception:
                # If we can't get details, include basic info without children
                enriched.append({
                    "id": loc.get("id"),
                    "name": loc.get("name"),
                    "description": loc.get("description", ""),
                    "itemCount": loc.get("itemCount", 0),
                    "children": [],
                })

        return enriched
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to fetch location tree: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{location_id}")
async def get_location(
    location_id: str,
    token: Annotated[str, Depends(get_token)],
) -> dict[str, Any]:
    """Fetch a specific location by ID with its children.

    Args:
        location_id: The ID of the location to fetch.
        token: Bearer token from login (extracted from header).

    Returns:
        Location object including children.
    """
    client = get_client()

    try:
        return await client.get_location(token, location_id)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to fetch location {location_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
