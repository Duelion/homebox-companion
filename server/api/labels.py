"""Labels API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from homebox_companion import HomeboxClient

from ..dependencies import get_client, get_token

router = APIRouter()


@router.get("/labels")
async def get_labels(
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> list[dict[str, Any]]:
    """Fetch all available labels.

    Exceptions (AuthenticationError, RuntimeError) are handled by
    the centralized domain_error_handler in app.py.
    """
    return await client.list_labels(token)









