"""Authentication API routes."""

import socket

import httpx
from fastapi import APIRouter, HTTPException
from loguru import logger

from homebox_companion import AuthenticationError
from ..dependencies import get_client
from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


def _get_friendly_error_message(error: Exception) -> str:
    """Convert technical errors to user-friendly messages."""
    error_str = str(error).lower()
    
    # DNS resolution failure
    if "getaddrinfo failed" in error_str or isinstance(error.__cause__, socket.gaierror):
        return "Cannot connect to Homebox server. The server address could not be resolved. Please verify the HBC_HOMEBOX_URL is correct."
    
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








