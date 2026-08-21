"""Configuration API routes."""

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel

from homebox_companion import settings
from homebox_companion.homebox.client import HomeboxClient

from ..dependencies import get_client

router = APIRouter()

_STATUS_CACHE_TTL_SECONDS = 60.0
_status_cache: dict[str, Any] | None = None
_status_cache_at: float = 0.0


class HomeboxOidcStatus(BaseModel):
    """OIDC configuration exposed from Homebox /api/v1/status."""

    enabled: bool
    allow_local: bool
    button_text: str = ""
    auto_redirect: bool = False


class ConfigResponse(BaseModel):
    """Safe configuration information for the frontend."""

    is_demo_mode: bool
    # Explicit demo mode from HBC_DEMO_MODE env var only (not URL detection).
    # Used for security-sensitive features like disabling chat.
    demo_mode_explicit: bool
    homebox_url: str
    llm_model: str
    update_check_enabled: bool
    image_quality: str
    log_level: str
    capture_max_images: int
    capture_max_file_size_mb: int
    print_enabled: bool
    homebox_oidc: HomeboxOidcStatus | None = None


def _parse_oidc_status(status_data: dict[str, Any]) -> HomeboxOidcStatus:
    oidc = status_data.get("oidc") or {}
    return HomeboxOidcStatus(
        enabled=bool(oidc.get("enabled")),
        allow_local=bool(oidc.get("allowLocal", True)),
        button_text=str(oidc.get("buttonText") or ""),
        auto_redirect=bool(oidc.get("autoRedirect")),
    )


async def _get_cached_homebox_oidc(client: HomeboxClient) -> HomeboxOidcStatus | None:
    """Fetch Homebox OIDC status with a short in-memory cache."""
    global _status_cache, _status_cache_at

    now = time.time()
    if _status_cache is not None and now - _status_cache_at < _STATUS_CACHE_TTL_SECONDS:
        return _parse_oidc_status(_status_cache)

    try:
        status_data = await client.get_status()
        _status_cache = status_data
        _status_cache_at = now
        return _parse_oidc_status(status_data)
    except Exception as e:
        logger.debug(f"Failed to fetch Homebox status for OIDC config: {e}")
        return None


@router.get("/config", response_model=ConfigResponse)
async def get_config(
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> ConfigResponse:
    """Return safe configuration information.

    This endpoint exposes non-sensitive configuration
    for display in the Settings page.
    """
    homebox_oidc = await _get_cached_homebox_oidc(client)

    return ConfigResponse(
        is_demo_mode=settings.is_demo_mode,
        demo_mode_explicit=settings.demo_mode,
        homebox_url=settings.effective_link_base_url,
        llm_model=settings.effective_llm_model,
        update_check_enabled=not settings.disable_update_check,
        image_quality=settings.image_quality.value,
        log_level=settings.log_level,
        capture_max_images=settings.capture_max_images,
        capture_max_file_size_mb=settings.capture_max_file_size_mb,
        print_enabled=settings.print_enabled,
        homebox_oidc=homebox_oidc,
    )
