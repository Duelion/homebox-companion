"""Configuration API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from homebox_companion import settings

router = APIRouter()


class ConfigResponse(BaseModel):
    """Safe configuration information for the frontend."""

    is_demo_mode: bool
    homebox_url: str
    llm_model: str
    update_check_enabled: bool
    image_quality: str
    log_level: str
    capture_max_images: int
    capture_max_file_size_mb: int


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Return safe configuration information.

    This endpoint exposes non-sensitive configuration
    for display in the Settings page.
    """
    return ConfigResponse(
        is_demo_mode=settings.is_demo_mode,
        homebox_url=settings.homebox_url,
        llm_model=settings.effective_llm_model,
        update_check_enabled=not settings.disable_update_check,
        image_quality=settings.image_quality.value,
        log_level=settings.log_level,
        capture_max_images=settings.capture_max_images,
        capture_max_file_size_mb=settings.capture_max_file_size_mb,
    )

