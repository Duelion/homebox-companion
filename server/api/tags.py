"""Tags API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from homebox_companion import HomeboxGateway

from ..dependencies import get_gateway

router = APIRouter()


@router.get("/tags")
async def get_tags(
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> list[dict[str, Any]]:
    """Fetch all available tags.

    Exceptions (HomeboxAuthError, RuntimeError) are handled by
    the centralized domain_error_handler in app.py.
    """
    return await gateway.list_tags()
