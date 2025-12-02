"""FastAPI application factory for Homebox Companion."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from homebox_companion import HomeboxClient, settings, setup_logging
from homebox_companion.core.logging import logger

from .api import api_router
from .dependencies import set_client

# Get version
try:
    __version__ = version("homebox-companion")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared resources across the app lifecycle."""
    # Setup
    setup_logging()
    logger.info("Starting Homebox Companion API")
    logger.info(f"Version: {__version__}")
    logger.info(f"Homebox API URL: {settings.api_url}")
    logger.info(f"OpenAI Model: {settings.openai_model}")

    if settings.is_demo_mode:
        logger.warning("Using demo server - set HBC_API_URL for your own instance")

    # Validate settings on startup
    for issue in settings.validate():
        logger.warning(issue)

    # Create and set the shared client
    client = HomeboxClient(base_url=settings.api_url)
    set_client(client)

    yield

    # Cleanup
    await client.aclose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Homebox Companion",
        description="AI-powered tools for Homebox inventory management",
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

    # Include API routes
    app.include_router(api_router)

    # Version endpoint
    @app.get("/api/version")
    async def get_version() -> dict[str, str]:
        """Return the application version."""
        return {"version": __version__}

    # Serve static frontend files
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Serve index.html for root
    @app.get("/")
    async def serve_index() -> FileResponse:
        """Serve the main HTML page."""
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        # If no static frontend, return API info
        from fastapi.responses import JSONResponse

        return JSONResponse({
            "name": "Homebox Companion API",
            "version": __version__,
            "docs": "/docs",
        })

    return app


# Default app instance for uvicorn
app = create_app()


def run():
    """Entry point for the homebox-companion CLI command."""
    import uvicorn

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
    )


if __name__ == "__main__":
    run()

