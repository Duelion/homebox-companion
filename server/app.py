"""FastAPI application factory for Homebox Companion."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from homebox_companion import HomeboxClient, settings, setup_logging
from homebox_companion.core.logging import logger

from .api import api_router
from .dependencies import set_client

# GitHub version check cache
_version_cache: dict[str, str | float | None] = {
    "latest_version": None,
    "last_check": 0.0,
}
VERSION_CACHE_TTL = 3600  # 1 hour in seconds

# Get version
try:
    __version__ = version("homebox-companion")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers for comparison."""
    # Strip leading 'v' if present
    version_str = version_str.lstrip("v")
    # Handle dev versions
    if ".dev" in version_str:
        version_str = version_str.split(".dev")[0]
    # Parse major.minor.patch
    parts = version_str.split(".")
    return tuple(int(p) for p in parts if p.isdigit())


def _is_newer_version(latest: str, current: str) -> bool:
    """Check if latest version is newer than current version."""
    try:
        latest_parts = _parse_version(latest)
        current_parts = _parse_version(current)
        return latest_parts > current_parts
    except (ValueError, AttributeError):
        return False


async def _get_latest_github_version() -> str | None:
    """Fetch the latest release version from GitHub with caching."""
    global _version_cache

    # Check if cache is still valid
    now = time.time()
    if (
        _version_cache["latest_version"] is not None
        and now - float(_version_cache["last_check"]) < VERSION_CACHE_TTL
    ):
        return str(_version_cache["latest_version"])

    # Fetch from GitHub
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{settings.github_repo}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                _version_cache["latest_version"] = latest_version
                _version_cache["last_check"] = now
                return latest_version
    except Exception as e:
        logger.debug(f"Failed to fetch latest version from GitHub: {e}")

    return None


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
    for issue in settings.validate_config():
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
    async def get_version(force_check: bool = False) -> dict[str, str | bool | None]:
        """Return the application version and update availability.

        Args:
            force_check: If True, check for updates even if HBC_DISABLE_UPDATE_CHECK is set.
                        Useful for Settings page where user explicitly wants to see updates.
        """
        result: dict[str, str | bool | None] = {"version": __version__}

        # Check for updates if enabled OR if force_check is requested
        if not settings.disable_update_check or force_check:
            latest_version = await _get_latest_github_version()
            result["latest_version"] = latest_version
            result["update_available"] = (
                _is_newer_version(latest_version, __version__)
                if latest_version
                else False
            )
        else:
            result["latest_version"] = None
            result["update_available"] = False

        return result

    # Serve static frontend files (SvelteKit SPA)
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    if os.path.isdir(static_dir):
        # Mount static files at root to serve _app/, favicon, etc.
        # This must come after API routes so /api/* takes priority
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    # SPA fallback - serve index.html for any unmatched routes
    # Note: With html=True on StaticFiles, this handles SPA routing automatically
    # But we add explicit handler for better control
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        """Serve index.html for client-side routing (SPA fallback)."""
        # Don't fallback for API routes - let them 404 normally
        if request.url.path.startswith("/api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=404,
                content={"detail": "Not Found"}
            )
        # Serve index.html for all other 404s (SPA client-side routing)
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        # No frontend built yet
        from fastapi.responses import JSONResponse
        return JSONResponse({
            "name": "Homebox Companion API",
            "version": __version__,
            "docs": "/docs",
            "note": "Frontend not built. Run: cd frontend && npm run build"
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

