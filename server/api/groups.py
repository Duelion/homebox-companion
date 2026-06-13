"""Groups (collections) API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from homebox_companion import HomeboxClient

from ..dependencies import get_client, get_token

router = APIRouter()


@router.get("/groups")
async def get_groups(
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> list[dict[str, Any]]:
    """Get all collections the authenticated user belongs to."""
    return await client.list_groups(token)
