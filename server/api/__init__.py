"""API routers aggregation."""

from fastapi import APIRouter

from .auth import router as auth_router
from .chat import router as chat_router
from .config import router as config_router
from .debug import router as debug_router
from .field_preferences import router as field_preferences_router
from .items import router as items_router
from .labels import router as labels_router
from .locations import router as locations_router
from .logs import router as logs_router
from .mcp import router as mcp_router
from .ai_config import router as ai_config_router
from .app_preferences import router as app_preferences_router
from .enrichment import router as enrichment_router
from .ollama import router as ollama_router
from .sessions import router as sessions_router
from .tools.vision import router as vision_router

# Main API router
api_router = APIRouter(prefix="/api")

# Include all sub-routers
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(config_router, tags=["config"])
api_router.include_router(field_preferences_router, tags=["settings"])
api_router.include_router(locations_router, tags=["locations"])
api_router.include_router(labels_router, tags=["labels"])
api_router.include_router(items_router, tags=["items"])
api_router.include_router(logs_router, tags=["logs"])
api_router.include_router(mcp_router, tags=["mcp"])
api_router.include_router(vision_router, prefix="/tools/vision", tags=["vision"])
api_router.include_router(ollama_router, tags=["ollama"])
api_router.include_router(sessions_router, tags=["sessions"])
api_router.include_router(ai_config_router, tags=["ai-config"])
api_router.include_router(app_preferences_router, tags=["settings"])
api_router.include_router(enrichment_router, tags=["enrichment"])
api_router.include_router(debug_router, tags=["debug"])

__all__ = ["api_router"]
