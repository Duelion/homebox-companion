"""Location API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException

from homebox_companion import AuthenticationError

from ..dependencies import get_client, get_token
from ..schemas.locations import LocationCreate, LocationUpdate

router = APIRouter()


@router.get("/locations")
async def get_locations(
    authorization: Annotated[str | None, Header()] = None,
    filter_children: bool | None = None,
) -> list[dict[str, Any]]:
    """Fetch all available locations.

    Args:
        filter_children: If true, returns only top-level locations.
    """
    token = get_token(authorization)
    client = get_client()
    try:
        return await client.list_locations(token, filter_children=filter_children)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/locations/tree")
async def get_locations_tree(
    authorization: Annotated[str | None, Header()] = None,
) -> list[dict[str, Any]]:
    """Fetch top-level locations with children info for hierarchical navigation."""
    token = get_token(authorization)
    client = get_client()
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/locations/{location_id}")
async def get_location(
    location_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Fetch a specific location by ID with its children enriched with their own children info."""
    token = get_token(authorization)
    client = get_client()
    try:
        location = await client.get_location(token, location_id)
        
        # Enrich children with their own children info (for nested navigation)
        children = location.get("children", [])
        if children:
            enriched_children = []
            for child in children:
                try:
                    # Fetch full details for each child to get their children
                    child_details = await client.get_location(token, child["id"])
                    enriched_children.append({
                        "id": child_details.get("id"),
                        "name": child_details.get("name"),
                        "description": child_details.get("description", ""),
                        "itemCount": child.get("itemCount", 0),
                        "children": child_details.get("children", []),
                    })
                except Exception:
                    # If we can't get details, include basic info without children
                    enriched_children.append({
                        "id": child.get("id"),
                        "name": child.get("name"),
                        "description": child.get("description", ""),
                        "itemCount": child.get("itemCount", 0),
                        "children": [],
                    })
            location["children"] = enriched_children
        
        return location
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/locations")
async def create_location(
    data: LocationCreate,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Create a new location."""
    token = get_token(authorization)
    client = get_client()
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
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Update an existing location."""
    token = get_token(authorization)
    client = get_client()
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





