"""Authentication API routes."""

from typing import Annotated

from fastapi import APIRouter, Header
from loguru import logger

from homebox_companion import settings

from ..dependencies import get_client, get_token
from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate with Homebox and return bearer token.

    Connection and authentication errors are wrapped by the client layer
    and handled by the centralized exception handler in app.py.
    """
    logger.info("Login attempt")

    # Log configuration for debugging
    logger.debug(f"Login: HBC_HOMEBOX_URL configured as: {settings.homebox_url}")
    logger.debug(f"Login: Full API URL will be: {settings.api_url}")

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
