"""Location API routes."""

import asyncio
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from loguru import logger

from homebox_companion import HomeboxClient

from ..dependencies import get_client, get_token
from ..schemas.locations import LocationCreate, LocationUpdate

router = APIRouter()

_DIGIT_RUN = re.compile(r"(\d+)")


def natural_sort_key(name: str) -> tuple[tuple[int, int | str], ...]:
    """Sort key that orders embedded numbers numerically (1, 2, 10 instead of 1, 10, 2).

    Homebox returns siblings in plain lexicographic order, which scrambles
    numbered containers. Each digit run is compared as an integer; text runs
    are compared case-insensitively. Numeric parts sort before text parts so
    mixed-type comparisons stay well-defined.
    """
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in _DIGIT_RUN.split(name)
    )


def sort_tree_naturally(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recursively sort tree nodes (and their children) by name using natural order."""
    for node in nodes:
        children = node.get("children")
        if children:
            node["children"] = sort_tree_naturally(children)
    return sorted(nodes, key=lambda n: natural_sort_key(str(n.get("name") or "")))


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
    """Fetch the full recursive location tree for hierarchical navigation and search.

    Uses the native Homebox tree endpoint which returns all nesting levels,
    ensuring deeply nested locations are visible in search results.
    """
    return sort_tree_naturally(await client.get_location_tree(token))


@router.get("/locations/{location_id}")
async def get_location(
    location_id: str,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> dict[str, Any]:
    """Fetch a specific location by ID with its children enriched with their own children info."""
    # Fetch location details and flat list (for itemCount) in parallel
    location, all_locations = await asyncio.gather(
        client.get_location(token, location_id),
        client.list_locations(token),
    )
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
        location["children"] = sorted(
            enriched_children, key=lambda c: natural_sort_key(str(c.get("name") or ""))
        )

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
