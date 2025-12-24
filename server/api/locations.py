"""Location API routes."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from homebox_companion import AuthenticationError, HomeboxClient

from ..dependencies import get_client, get_token
from ..schemas.locations import LocationCreate, LocationUpdate

router = APIRouter()


@router.get("/locations")
async def get_locations(
    filter_children: bool | None = Query(None),
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> list[dict[str, Any]]:
    """Fetch all available locations.

    Args:
        filter_children: If true, returns only top-level locations.
    """
    try:
        return await client.list_locations(token, filter_children=filter_children)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/locations/tree")
async def get_locations_tree(
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> list[dict[str, Any]]:
    """Fetch top-level locations with children info for hierarchical navigation."""
    try:
        # Get only top-level locations
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
            except Exception as e:
                # If we can't get details, include basic info without children
                logger.warning(f"Failed to get details for location {loc.get('id')}: {e}")
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/locations/{location_id}")
async def get_location(
    location_id: str,
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> dict[str, Any]:
    """Fetch a specific location by ID with its children enriched with their own children info."""
    try:
        location = await client.get_location(token, location_id)

        # Fetch flat location list to get accurate itemCount for all locations
        all_locations = await client.list_locations(token)
        itemcount_lookup = {loc["id"]: loc.get("itemCount", 0) for loc in all_locations}

        # Enrich the location itself with itemCount
        location["itemCount"] = itemcount_lookup.get(location_id, location.get("itemCount", 0))

        # Enrich children with their own children info (for nested navigation)
        children = location.get("children", [])
        if children:
            # Fetch all child details in parallel for better performance
            async def fetch_child_details(child: dict[str, Any]) -> dict[str, Any]:
                try:
                    child_details = await client.get_location(token, child["id"])
                    return {
                        "id": child_details.get("id"),
                        "name": child_details.get("name"),
                        "description": child_details.get("description", ""),
                        "itemCount": itemcount_lookup.get(child["id"], 0),
                        "children": child_details.get("children", []),
                    }
                except Exception as e:
                    # If we can't get details, include basic info without children
                    child_id = child.get("id")
                    logger.warning(f"Failed to get details for child location {child_id}: {e}")
                    return {
                        "id": child.get("id"),
                        "name": child.get("name"),
                        "description": child.get("description", ""),
                        "itemCount": itemcount_lookup.get(child.get("id", ""), 0),
                        "children": [],
                    }

            enriched_children = await asyncio.gather(
                *[fetch_child_details(child) for child in children]
            )
            location["children"] = list(enriched_children)

        return location
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/locations")
async def create_location(
    data: LocationCreate,
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> dict[str, Any]:
    """Create a new location."""
    try:
        return await client.create_location(
            token,
            name=data.name,
            description=data.description,
            parent_id=data.parent_id,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/locations/{location_id}")
async def update_location(
    location_id: str,
    data: LocationUpdate,
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> dict[str, Any]:
    """Update an existing location."""
    try:
        return await client.update_location(
            token,
            location_id=location_id,
            name=data.name,
            description=data.description,
            parent_id=data.parent_id,
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
