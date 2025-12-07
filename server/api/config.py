"""Configuration API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from homebox_companion import settings

router = APIRouter()


class ConfigResponse(BaseModel):
    """Safe configuration information for the frontend."""

    is_demo_mode: bool
    openai_model: str
    update_check_enabled: bool


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Return safe configuration information.

    This endpoint exposes non-sensitive configuration
    for display in the Settings page.
    """
    return ConfigResponse(
        is_demo_mode=settings.is_demo_mode,
        openai_model=settings.openai_model,
        update_check_enabled=not settings.disable_update_check,
    )

