"""Location API routes."""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from loguru import logger

from homebox_companion import HomeboxClient

from ..dependencies import get_client, get_token
from ..schemas.locations import LocationCreate, LocationUpdate

router = APIRouter()


@router.get("/locations")
async def get_locations(
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
    filter_children: bool | None = Query(None),
) -> list[dict[str, Any]]:
    """Fetch all available locations.

    Args:
        filter_children: If true, returns only top-level locations.
    """
    return await client.list_locations(token, filter_children=filter_children)


@router.get("/locations/tree")
async def get_locations_tree(
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> list[dict[str, Any]]:
    """Fetch top-level locations with children info for hierarchical navigation."""
    # Get only top-level locations
    top_level = await client.list_locations(token, filter_children=True)

    async def fetch_location_details(loc: dict[str, Any]) -> dict[str, Any]:
        """Fetch details for a single location with graceful degradation."""
        try:
            details = await client.get_location(token, loc["id"])
            return {
                "id": details.get("id"),
                "name": details.get("name"),
                "description": details.get("description", ""),
                "itemCount": loc.get("itemCount", 0),
                "children": details.get("children", []),
            }
        except Exception as e:
            # Graceful degradation: if we can't get details, include basic info
            logger.warning(f"Failed to get details for location {loc.get('id')}: {e}")
            return {
                "id": loc.get("id"),
                "name": loc.get("name"),
                "description": loc.get("description", ""),
                "itemCount": loc.get("itemCount", 0),
                "children": [],
            }

    # Fetch all location details in parallel for better performance
    enriched = await asyncio.gather(*[fetch_location_details(loc) for loc in top_level])

    return list(enriched)


@router.get("/locations/{location_id}")
async def get_location(
    location_id: str,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> dict[str, Any]:
    """Fetch a specific location by ID with its children enriched with their own children info."""
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
                # Graceful degradation: if we can't get details, include basic info
                child_id = child.get("id")
                logger.warning(f"Failed to get details for child location {child_id}: {e}")
                return {
                    "id": child.get("id"),
                    "name": child.get("name"),
                    "description": child.get("description", ""),
                    "itemCount": itemcount_lookup.get(child.get("id", ""), 0),
                    "children": [],
                }

        enriched_children = await asyncio.gather(*[fetch_child_details(child) for child in children])
        location["children"] = list(enriched_children)

    return location


@router.post("/locations")
async def create_location(
    data: LocationCreate,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> dict[str, Any]:
    """Create a new location."""
    return await client.create_location(
        token,
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
    )


@router.put("/locations/{location_id}")
async def update_location(
    location_id: str,
    data: LocationUpdate,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> dict[str, Any]:
    """Update an existing location."""
    return await client.update_location(
        token,
        location_id=location_id,
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
    )
