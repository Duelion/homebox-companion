"""Tags API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from homebox_companion import HomeboxClient

from ..dependencies import get_client, get_token

router = APIRouter()


@router.get("/tags")
async def get_tags(
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> list[dict[str, Any]]:
    """Fetch all available tags.

    Exceptions (HomeboxAuthError, RuntimeError) are handled by
    the centralized domain_error_handler in app.py.
    """
    return await client.list_tags(token)
