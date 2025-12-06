"""Labels API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException

from homebox_companion import AuthenticationError

from ..dependencies import get_client, get_token

router = APIRouter()


@router.get("/labels")
async def get_labels(
    authorization: Annotated[str | None, Header()] = None,
) -> list[dict[str, Any]]:
    """Fetch all available labels."""
    token = get_token(authorization)
    client = get_client()
    try:
        return await client.list_labels(token)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e








