"""Labels API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from homebox_companion import AuthenticationError, HomeboxClient

from ..dependencies import get_client, get_token

router = APIRouter()


@router.get("/labels")
async def get_labels(
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> list[dict[str, Any]]:
    """Fetch all available labels."""
    try:
        return await client.list_labels(token)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e









