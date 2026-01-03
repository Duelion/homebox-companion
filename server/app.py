"""FastAPI application factory for Homebox Companion."""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.responses import Response

from homebox_companion import (
    HomeboxClient,
    HomeboxCompanionError,
    settings,
    setup_logging,
)

from .api import api_router
from .dependencies import client_holder, session_store_holder, tool_executor_holder
from .middleware import RequestIDMiddleware, request_id_var

# GitHub version check cache with async lock for thread safety within a single worker.
# NOTE: This cache is per-worker. When running with multiple workers (e.g., uvicorn --workers N),
# each worker maintains its own cache. This is acceptable since version checks are infrequent
# and the TTL ensures reasonable freshness. For shared caching across workers, use Redis.
_version_cache: dict[str, str | float | None] = {
    "latest_version": None,
    "last_check": 0.0,
}
_version_cache_lock = asyncio.Lock()
VERSION_CACHE_TTL = 3600  # 1 hour in seconds
VERSION_CACHE_NEGATIVE_TTL = 300  # 5 minutes for failed checks

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
    """Fetch the latest release version from GitHub with caching and proper error handling.

    Implements both positive caching (1 hour for successful checks) and negative caching
    (5 minutes for failed checks) to prevent hammering the GitHub API during outages.

    Uses double-checked locking to minimize lock hold time: first checks cache without
    lock, then acquires lock only when refresh is needed and re-checks to avoid
    thundering herd.
    """
    now = time.time()

    # Quick cache check without lock (cache reads are safe)
    last_check = _version_cache["last_check"]
    if isinstance(last_check, (int, float)) and last_check > 0:
        # If we have a cached version, use positive TTL
        if _version_cache["latest_version"] is not None:
            if now - last_check < VERSION_CACHE_TTL:
                return str(_version_cache["latest_version"])
        # If last check failed (no version), use negative TTL
        else:
            if now - last_check < VERSION_CACHE_NEGATIVE_TTL:
                logger.debug("Using negative cache for version check")
                return None

    # Cache miss or expired - acquire lock for refresh
    async with _version_cache_lock:
        # Double-check after acquiring lock (another request may have refreshed)
        now = time.time()  # Refresh timestamp
        last_check = _version_cache["last_check"]
        if isinstance(last_check, (int, float)) and last_check > 0:
            if _version_cache["latest_version"] is not None:
                if now - last_check < VERSION_CACHE_TTL:
                    return str(_version_cache["latest_version"])
            else:
                if now - last_check < VERSION_CACHE_NEGATIVE_TTL:
                    return None

        # Still need to refresh - do the fetch while holding lock
        # (This serializes refreshes but is acceptable since they're infrequent)
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
                    logger.debug(f"Fetched latest version from GitHub: {latest_version}")
                    return latest_version
                else:
                    # Non-200 status: update last_check for negative caching
                    _version_cache["last_check"] = now
                    _version_cache["latest_version"] = None
                    if response.status_code == 404:
                        logger.warning(
                            f"GitHub repository {settings.github_repo} not found "
                            "or no releases available"
                        )
                    elif response.status_code == 403:
                        logger.warning(
                            "GitHub API rate limit exceeded. Update check will retry later."
                        )
                    else:
                        logger.warning(
                            f"GitHub API returned unexpected status {response.status_code}"
                        )
        except httpx.TimeoutException:
            _version_cache["last_check"] = now
            _version_cache["latest_version"] = None
            logger.warning("GitHub version check timed out. Update check will retry later.")
        except httpx.NetworkError as e:
            _version_cache["last_check"] = now
            _version_cache["latest_version"] = None
            logger.warning(f"Network error checking for updates: {e}")
        except (ValueError, KeyError) as e:
            _version_cache["last_check"] = now
            _version_cache["latest_version"] = None
            logger.warning(f"Invalid response from GitHub API: {e}")
        except Exception as e:
            # Catch-all for unexpected errors, but still log prominently
            _version_cache["last_check"] = now
            _version_cache["latest_version"] = None
            logger.error(f"Unexpected error checking for updates: {e}", exc_info=True)

        return None


async def _test_homebox_connectivity() -> None:
    """Test connectivity to Homebox server and log diagnostic information.

    Only runs when log level is DEBUG. Helps diagnose connection issues
    by testing DNS resolution and HTTP connectivity.
    """
    if settings.log_level.upper() != "DEBUG":
        return

    import socket
    from urllib.parse import urlparse

    parsed = urlparse(settings.homebox_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    logger.debug(f"Connectivity test: Target URL: {settings.homebox_url}")
    logger.debug(f"Connectivity test: Parsed host: {host}, port: {port}, scheme: {parsed.scheme}")

    # Test DNS resolution
    if host:
        try:
            addresses = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            logger.debug(f"Connectivity test: DNS resolved {host} to {len(addresses)} address(es)")
            for addr in addresses[:5]:  # Show up to 5 addresses
                family, socktype, proto, canonname, sockaddr = addr
                family_name = "IPv4" if family == socket.AF_INET else "IPv6"
                logger.debug(f"Connectivity test:   {family_name}: {sockaddr[0]}:{sockaddr[1]}")
        except socket.gaierror as e:
            logger.warning(f"Connectivity test: DNS resolution failed for {host}: {e}")
            if host in ("localhost", "127.0.0.1"):
                logger.warning(
                    "Connectivity test: Using localhost from Docker container won't work. "
                    "Use 'host.docker.internal' (Docker Desktop) or the host's actual IP."
                )
            return

    # Test HTTP connectivity
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Just do a HEAD request to check connectivity
            response = await client.head(settings.homebox_url)
            logger.debug(
                f"Connectivity test: HEAD {settings.homebox_url} -> {response.status_code}"
            )
            if response.status_code in (301, 302, 307, 308):
                redirect_location = response.headers.get("location")
                logger.debug(f"Connectivity test: Redirect to: {redirect_location}")
    except httpx.ConnectError as e:
        logger.warning(f"Connectivity test: Connection failed: {e}")
    except httpx.TimeoutException:
        logger.warning("Connectivity test: Connection timed out")
    except Exception as e:
        logger.warning(f"Connectivity test: Unexpected error: {type(e).__name__}: {e}")


class CachedStaticFiles(StaticFiles):
    """StaticFiles with proper cache control headers for cache busting."""

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)

        # index.html and root: always revalidate
        #
        # service-worker.js must also always revalidate:
        # - browsers may cache the SW script itself
        # - if cached, clients can stay stuck on old SW logic for up to the TTL
        #
        # manifest.json is also frequently cached by browsers/PWA install flows.
        if path in ("", "index.html", "service-worker.js", "manifest.json") or path.endswith(
            "/index.html"
        ):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        # Immutable hashed assets: cache forever
        elif "/_app/immutable/" in f"/{path}" or path.startswith("_app/immutable/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        # Other static assets (icons, manifest, etc.): cache for 1 hour
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage shared resources across the app lifecycle."""
    # Setup
    setup_logging()
    logger.info("Starting Homebox Companion API")
    logger.info(f"Version: {__version__}")
    logger.info(f"Homebox URL (HBC_HOMEBOX_URL): {settings.homebox_url}")
    logger.info(f"Full API endpoint: {settings.api_url}")
    logger.info(f"LLM Model: {settings.effective_llm_model}")
    logger.info(f"Log level: {settings.log_level}")

    if settings.using_legacy_openai_env:
        logger.warning(
            "DEPRECATION WARNING: You are using legacy environment variables "
            "(HBC_OPENAI_API_KEY and/or HBC_OPENAI_MODEL). "
            "Please migrate to HBC_LLM_API_KEY and HBC_LLM_MODEL. "
            "The legacy variables are supported for backward compatibility but may be "
            "removed in a future version."
        )

    # Check for demo conditions and log appropriately
    is_using_demo_server = "demo.homebox.software" in settings.homebox_url.lower()
    if is_using_demo_server:
        logger.warning("Using demo server - set HBC_HOMEBOX_URL for your own instance")
    elif settings.demo_mode:
        logger.info("Demo mode enabled (HBC_DEMO_MODE=true)")

    # Validate settings on startup
    for issue in settings.validate_config():
        logger.warning(issue)

    # Run connectivity test in debug mode
    await _test_homebox_connectivity()

    # Initialize shared service holders
    client = HomeboxClient(base_url=settings.api_url)
    client_holder.set(client)

    # Session store and executor are lazily initialized on first use
    # (see their .get() methods in dependencies.py)

    yield

    # Cleanup
    logger.info("Shutting down Homebox Companion API")

    # Reset holders (executor and session store don't need async cleanup)
    tool_executor_holder.reset()
    session_store_holder.reset()
    await client_holder.close()
    # Note: cleanup_llm_clients() is now a no-op with LiteLLM
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Homebox Companion",
        description="AI-powered tools for Homebox inventory management",
        version=__version__,
        lifespan=lifespan,
    )

    # Request-ID middleware (must be added first to wrap all requests)
    app.add_middleware(RequestIDMiddleware)  # type: ignore[arg-type]

    # CORS middleware for browser access
    # Use HBC_CORS_ORIGINS to restrict origins in production
    app.add_middleware(
        CORSMiddleware,  # type: ignore[arg-type]
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Log security settings
    if settings.cors_origins == "*":
        logger.debug("CORS: Allowing all origins (set HBC_CORS_ORIGINS to restrict)")
    else:
        logger.info(f"CORS: Restricted to origins: {settings.cors_origins_list}")

    # Include API routes
    app.include_router(api_router)

    # Unified exception handler for all domain exceptions
    # Routes can raise domain exceptions directly without wrapping in HTTPException
    @app.exception_handler(HomeboxCompanionError)
    async def domain_error_handler(request, exc: HomeboxCompanionError):
        """Convert domain exceptions to appropriate HTTP responses.

        - Logs with appropriate level and exception chain
        - Returns structured JSON with error code and user message
        - Includes request-ID in response header for correlation
        """
        # Log with appropriate level and include exception chain
        log_method = getattr(logger, exc.log_level, logger.error)
        log_method(
            f"{exc.error_code}: {exc.to_dict()}",
            exc_info=exc if exc.log_level == "error" else None,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.user_message,
                "code": exc.error_code,
            },
            headers={"X-Request-ID": request_id_var.get()},
        )

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
                _is_newer_version(latest_version, __version__) if latest_version else False
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
        app.mount("/", CachedStaticFiles(directory=static_dir, html=True), name="static")

    # SPA fallback - serve index.html for any unmatched routes
    # Note: With html=True on StaticFiles, this handles SPA routing automatically
    # But we add explicit handler for better control
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        """Serve index.html for client-side routing (SPA fallback)."""
        # Don't fallback for API routes - let them 404 normally
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        # Serve index.html for all other 404s (SPA client-side routing)
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            response = FileResponse(index_path)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        # No frontend built yet
        return JSONResponse(
            {
                "name": "Homebox Companion API",
                "version": __version__,
                "docs": "/docs",
                "note": "Frontend not built. Run: cd frontend && npm run build",
            }
        )

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
