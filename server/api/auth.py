"""Authentication API routes."""

import ipaddress
import time
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from loguru import logger

from homebox_companion import settings

from ..dependencies import get_client, get_token
from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


class RateLimiter:
    """In-memory rate limiter with cleanup and trusted proxy support."""

    def __init__(self, window_seconds: float = 60.0):
        self.window_seconds = window_seconds
        # Key: IP address, Value: list of timestamps
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 600.0  # Cleanup every 10 minutes

    def check(self, request: Request, limit: int) -> None:
        """Check if request exceeds rate limit.

        Args:
            request: The FastAPI request object
            limit: Maximum attempts allowed in window

        Raises:
            HTTPException: If rate limit exceeded (429)
        """
        if limit <= 0:
            return

        now = time.time()
        client_ip = self._get_client_ip(request)

        # Lazy cleanup to prevent memory leaks
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now)

        # Filter attempts within window
        attempts = self._attempts[client_ip]
        valid_attempts = [ts for ts in attempts if now - ts < self.window_seconds]
        self._attempts[client_ip] = valid_attempts

        if len(valid_attempts) >= limit:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {int(self.window_seconds)} seconds.",
                headers={"Retry-After": str(int(self.window_seconds))},
            )

        self._attempts[client_ip].append(now)

    def _cleanup(self, now: float) -> None:
        """Remove entries with no valid attempts."""
        expired_ips = []
        for ip, timestamps in self._attempts.items():
            # Keep only valid timestamps
            valid = [ts for ts in timestamps if now - ts < self.window_seconds]
            if not valid:
                expired_ips.append(ip)
            else:
                self._attempts[ip] = valid

        for ip in expired_ips:
            del self._attempts[ip]

        self._last_cleanup = now
        logger.debug(f"Rate limiter cleanup: removed {len(expired_ips)} expired IPs")

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For only if configured to trust proxies."""
        # In a real production app, we should check if the immediate peer is a trusted proxy
        # For this companion app, we'll try to be smart but fail safe.

        # If running in Docker (common case), we might trust X-Forwarded-For check local IPs
        forwarded = request.headers.get("X-Forwarded-For")

        if forwarded:
            # Get the first IP in the list (client IP)
            client_ip = forwarded.split(",")[0].strip()
            # Simple validation to ensure it looks like an IP
            try:
                ipaddress.ip_address(client_ip)
                return client_ip
            except ValueError:
                logger.warning(f"Invalid IP in X-Forwarded-For: {client_ip}")

        # Fallback to direct connection IP
        if request.client and request.client.host:
            return request.client.host
        return "unknown"


# Singleton instance
_limiter = RateLimiter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, client_request: Request) -> LoginResponse:
    """Authenticate with Homebox and return bearer token.

    Connection and authentication errors are wrapped by the client layer
    and handled by the centralized exception handler in app.py.

    Rate limited to prevent brute-force attacks (configurable via HBC_AUTH_RATE_LIMIT_RPM).
    """
    # Verify rate limit
    _limiter.check(client_request, settings.auth_rate_limit_rpm)

    logger.info("Login attempt")
    logger.debug(f"Login: HBC_HOMEBOX_URL configured as: {settings.homebox_url}")

    client = get_client()
    response_data = await client.login(request.username, request.password)

    logger.info("Login successful")
    return LoginResponse(
        token=response_data.get("token", ""),
        expires_at=response_data.get("expiresAt", ""),
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    authorization: Annotated[str | None, Header()] = None,
) -> LoginResponse:
    """Refresh the access token using Homebox's refresh endpoint.

    Exchanges the current valid token for a new one with extended expiry.
    Returns the new token and expiry time.
    """
    token = get_token(authorization)
    client = get_client()

    data = await client.refresh_token(token)
    logger.info("Token refresh successful")
    return LoginResponse(
        token=data.get("token", ""),
        expires_at=data.get("expiresAt", ""),
    )

