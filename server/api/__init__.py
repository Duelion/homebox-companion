"""API routers aggregation."""

from fastapi import APIRouter

from .auth import router as auth_router
from .chat import router as chat_router
from .config import router as config_router
from .custom_fields import router as custom_fields_router
from .field_preferences import router as field_preferences_router
from .items import router as items_router
from .llm_profiles import router as llm_profiles_router
from .locations import router as locations_router
from .logs import router as logs_router
from .mcp import router as mcp_router
from .qr import router as qr_router
from .tags import router as tags_router
from .tools.vision import router as vision_router

# Main API router
api_router = APIRouter(prefix="/api")

# Include all sub-routers
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(config_router, tags=["config"])
api_router.include_router(custom_fields_router, tags=["settings"])
api_router.include_router(field_preferences_router, tags=["settings"])
api_router.include_router(llm_profiles_router, tags=["llm"])
api_router.include_router(locations_router, tags=["locations"])
api_router.include_router(tags_router, tags=["tags"])
api_router.include_router(items_router, tags=["items"])
api_router.include_router(logs_router, tags=["logs"])
api_router.include_router(mcp_router, tags=["mcp"])
api_router.include_router(qr_router, tags=["qr"])
api_router.include_router(vision_router, prefix="/tools/vision", tags=["vision"])

__all__ = ["api_router"]

