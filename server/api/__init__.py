"""API routers aggregation."""

from fastapi import APIRouter

from .auth import router as auth_router
from .items import router as items_router
from .labels import router as labels_router
from .locations import router as locations_router
from .tools.vision import router as vision_router

# Main API router
api_router = APIRouter(prefix="/api")

# Include all sub-routers
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(locations_router, tags=["locations"])
api_router.include_router(labels_router, tags=["labels"])
api_router.include_router(items_router, tags=["items"])
api_router.include_router(vision_router, prefix="/tools/vision", tags=["vision"])

__all__ = ["api_router"]






