"""Assets API routes for asset ID validation."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from homebox_companion import HomeboxClient

from ..dependencies import get_client, get_token

router = APIRouter()


@router.get("/assets/{asset_id}")
async def get_asset_by_id(
    asset_id: str,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> dict:
    """Check if an asset ID exists in Homebox.

    Returns the item info if found, raises 404 if not found.
    Used by frontend to validate asset IDs before submission.
    """
    logger.debug(f"Checking asset ID: {asset_id}")

    try:
        result = await client.get_item_by_asset_id(token, asset_id)
        if result:
            logger.debug(f"Asset ID {asset_id} found: {result.get('name')}")
            return {
                "item_id": result.get("id"),
                "item_name": result.get("name"),
                "asset_id": result.get("assetId", asset_id),
            }
        raise HTTPException(status_code=404, detail="Asset ID not found")
    except ValueError:
        # get_item_by_asset_id raises ValueError if no item found
        logger.debug(f"Asset ID {asset_id} not found")
        raise HTTPException(status_code=404, detail="Asset ID not found") from None
    except HTTPException:
        raise
    except Exception as e:
        # Log actual server errors and return 500, don't mask as 404
        logger.error(f"Server error checking asset ID {asset_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to check asset ID") from e
