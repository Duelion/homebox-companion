"""Authentication API routes."""

import socket
from typing import Annotated

import httpx
from fastapi import APIRouter, Header, HTTPException
from loguru import logger
from pydantic import BaseModel

from homebox_companion import AuthenticationError

from ..dependencies import get_client, get_token
from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


class ValidateResponse(BaseModel):
    """Token validation response."""
    valid: bool


def _get_friendly_error_message(error: Exception) -> str:
    """Convert technical errors to user-friendly messages."""
    error_str = str(error).lower()

    # DNS resolution failure
    if "getaddrinfo failed" in error_str or isinstance(error.__cause__, socket.gaierror):
        return (
            "Cannot connect to Homebox server. The server address could not be resolved. "
            "Please verify the HBC_HOMEBOX_URL is correct."
        )

    # Connection refused
    if "connection refused" in error_str or "actively refused" in error_str:
        return "Connection refused. Please check if Homebox is running and the port is correct."

    # Connection timeout
    if "timed out" in error_str or "timeout" in error_str:
        return "Connection timed out. Please check if the Homebox server is reachable."

    # SSL/TLS errors
    if "ssl" in error_str or "certificate" in error_str:
        return "SSL/TLS error. Please check if the server URL protocol (http/https) is correct."

    # Network unreachable
    if "network is unreachable" in error_str or "no route to host" in error_str:
        return "Network unreachable. Please check your network connection and server address."

    # Authentication errors from Homebox
    if isinstance(error, AuthenticationError):
        return "Invalid email or password. Please check your credentials."

    # HTTP errors
    if isinstance(error, httpx.HTTPStatusError):
        if error.response.status_code == 401:
            return "Invalid email or password. Please check your credentials."
        if error.response.status_code == 404:
            return "Homebox API not found. Please verify the server URL is correct."
        return f"Server returned an error (HTTP {error.response.status_code})."

    # Fallback: return original message for unknown errors
    return str(error)


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
        friendly_message = _get_friendly_error_message(e)
        raise HTTPException(status_code=401, detail=friendly_message) from e


@router.get("/validate", response_model=ValidateResponse)
async def validate_token(
    authorization: Annotated[str | None, Header()] = None,
) -> ValidateResponse:
    """Validate the current auth token against Homebox.

    Makes a lightweight call to /users/self to verify the token is still valid.
    Returns {valid: true} if valid, raises 401 if invalid.
    """
    token = get_token(authorization)
    client = get_client()

    try:
        # Use /users/self as a lightweight token validation endpoint
        response = await client.client.get(
            f"{client.base_url}/users/self",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        if response.is_success:
            return ValidateResponse(valid=True)

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Token expired or invalid")

        # Other errors - token might still be valid, but something else went wrong
        # Return valid=true to avoid false negatives
        logger.warning(f"Token validation got unexpected status: {response.status_code}")
        return ValidateResponse(valid=True)

    except httpx.RequestError as e:
        # Network error - can't validate, assume valid to avoid blocking user
        logger.warning(f"Token validation network error: {e}")
        return ValidateResponse(valid=True)








