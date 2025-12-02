"""FastAPI backend for the Homebox Vision Companion web app.

This is the application entry point that configures the FastAPI app,
middleware, and mounts the modular routers.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from homebox_vision import AsyncHomeboxClient, settings
from server.dependencies import set_homebox_client
from server.routers import (
    auth_router,
    detection_router,
    items_router,
    labels_router,
    locations_router,
)

# Application version - keep in sync with pyproject.toml
__version__ = "0.16.0"

# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    level=settings.log_level,
    colorize=True,
)
logger.add(
    "logs/homebox_vision_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
)

logger.info("Starting Homebox Vision Companion API")
logger.info(f"Homebox API URL: {settings.api_url}")
logger.info(f"OpenAI Model: {settings.openai_model}")
if settings.is_demo_mode:
    logger.warning("Using demo server - set HOMEBOX_VISION_API_URL for your own instance")

# Validate settings on startup
for issue in settings.validate():
    logger.warning(issue)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared resources across the app lifecycle."""
    # Initialize shared client
    client = AsyncHomeboxClient(base_url=settings.api_url)
    set_homebox_client(client)
    logger.info("Initialized shared Homebox client")

    yield

    # Cleanup
    await client.aclose()
    set_homebox_client(None)
    logger.info("Closed shared Homebox client")


app = FastAPI(
    title="Homebox Vision Companion",
    description="AI-powered item detection for Homebox inventory management",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(locations_router)
app.include_router(labels_router)
app.include_router(detection_router)
app.include_router(items_router)


@app.get("/api/version")
async def get_version() -> dict[str, str]:
    """Return the application version."""
    return {"version": __version__}


# Serve static frontend files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the main HTML page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    # For development, redirect to Vite dev server
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="http://localhost:5173")


def run():
    """Entry point for the homebox-vision CLI command."""
    import uvicorn

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
    )


if __name__ == "__main__":
    run()
