"""Authentication API routes."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from ..dependencies import get_client
from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate with Homebox and return bearer token."""
    logger.info(f"Login attempt for user: {request.username}")
    client = get_client()
    try:
        token = await client.login(request.username, request.password)
        logger.info(f"Login successful for user: {request.username}")
        return LoginResponse(token=token)
    except Exception as e:
        logger.warning(f"Login failed for user {request.username}: {e}")
        raise HTTPException(status_code=401, detail=str(e)) from e






