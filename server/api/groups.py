"""Groups (collections) API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from homebox_companion import HomeboxGateway

from ..dependencies import get_gateway

router = APIRouter()


@router.get("/groups")
async def get_groups(
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> list[dict[str, Any]]:
    """Get all collections the authenticated user belongs to."""
    return await gateway.list_groups()
