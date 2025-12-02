"""API routers for the Homebox Vision Companion.

This package contains feature-based routers that handle specific
domains of the application.
"""

from .auth import router as auth_router
from .detection import router as detection_router
from .items import router as items_router
from .labels import router as labels_router
from .locations import router as locations_router

__all__ = [
    "auth_router",
    "locations_router",
    "labels_router",
    "detection_router",
    "items_router",
]
