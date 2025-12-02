"""Authentication router for the Homebox Vision API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from server.dependencies import get_client
from server.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/api", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate with Homebox and return a bearer token.

    The returned token should be stored securely on the client and
    included in the Authorization header for subsequent requests.

    Args:
        request: Login credentials (username/email and password).

    Returns:
        A response containing the bearer token.

    Raises:
        HTTPException: If authentication fails (401).
    """
    logger.info(f"Login attempt for user: {request.username}")
    client = get_client()

    try:
        token = await client.login(request.username, request.password)
        logger.info(f"Login successful for user: {request.username}")
        return LoginResponse(token=token)
    except Exception as e:
        logger.warning(f"Login failed for user {request.username}: {e}")
        raise HTTPException(status_code=401, detail=str(e)) from e
