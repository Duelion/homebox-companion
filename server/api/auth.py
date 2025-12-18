"""Authentication API routes."""

import socket
import traceback
from typing import Annotated

import httpx
from fastapi import APIRouter, Header, HTTPException
from loguru import logger

from homebox_companion import AuthenticationError, settings

from ..dependencies import get_client, get_token
from ..schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


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

    # JSON parsing errors (common with reverse proxy issues)
    if "expecting value" in error_str or "jsondecodeerror" in error_str:
        return (
            "Server returned an invalid response (not JSON). "
            "This often happens when a reverse proxy returns an HTML page instead of "
            "forwarding to Homebox. Check that HBC_HOMEBOX_URL points directly to Homebox."
        )

    # Authentication errors from Homebox
    if isinstance(error, AuthenticationError):
        # Check if it's a JSON/response format issue vs actual auth failure
        auth_msg = str(error)
        if "invalid json" in auth_msg.lower() or "content-type" in auth_msg.lower():
            return auth_msg  # Return the detailed message from client
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


def _log_exception_chain(error: Exception, prefix: str = "") -> None:
    """Log essential exception information for debugging."""
    logger.debug(f"{prefix}Exception: {type(error).__name__}: {error}")

    # Log safe request/response metadata only (no headers or bodies)
    if hasattr(error, "request"):
        try:
            req = error.request
            logger.debug(f"{prefix}URL: {req.url}")
        except Exception:
            pass

    if hasattr(error, "response"):
        try:
            resp = error.response
            logger.debug(f"{prefix}Status: {resp.status_code}")
        except Exception:
            pass

    # Log the cause chain
    if error.__cause__:
        logger.debug(f"{prefix}Caused by:")
        _log_exception_chain(error.__cause__, prefix + "  ")
    elif error.__context__ and not error.__suppress_context__:
        logger.debug(f"{prefix}During:")
        _log_exception_chain(error.__context__, prefix + "  ")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Authenticate with Homebox and return bearer token."""
    logger.info("Login attempt")

    # Log configuration for debugging
    logger.debug(f"Login: HBC_HOMEBOX_URL configured as: {settings.homebox_url}")
    logger.debug(f"Login: Full API URL will be: {settings.api_url}")

    client = get_client()
    try:
        response_data = await client.login(request.username, request.password)
        # #region agent log
        import json;open(r'c:\Users\fsoza\PycharmProjects\homebox-companion\.cursor\debug.log','a').write(json.dumps({'location':'auth.py:113','message':'Production auth endpoint got login response','data':{'response_type':type(response_data).__name__,'response_keys':list(response_data.keys()) if isinstance(response_data, dict) else 'not_a_dict','extracted_token':response_data.get("token") if isinstance(response_data, dict) else 'cannot_extract'},'timestamp':__import__('time').time()*1000,'sessionId':'debug-session','runId':'initial','hypothesisId':'E'})+'\n')
        # #endregion
        logger.info("Login successful")
        return LoginResponse(
            token=response_data.get("token"),
            expires_at=response_data.get("expiresAt", ""),
        )
    except httpx.ConnectError as e:
        # Detailed logging for connection errors
        logger.warning("Login failed: Connection error")
        _log_exception_chain(e, "Login: ")

        # Check for common Docker networking issues
        url = settings.homebox_url
        if "localhost" in url or "127.0.0.1" in url:
            logger.warning(
                "Login: HBC_HOMEBOX_URL uses localhost/127.0.0.1. "
                "When running in Docker, use 'host.docker.internal' (Docker Desktop) "
                "or the host's actual IP address instead."
            )

        friendly_message = _get_friendly_error_message(e)
        raise HTTPException(status_code=503, detail=friendly_message) from e
    except httpx.TimeoutException as e:
        logger.warning("Login failed: Timeout")
        _log_exception_chain(e, "Login: ")
        friendly_message = _get_friendly_error_message(e)
        raise HTTPException(status_code=503, detail=friendly_message) from e
    except AuthenticationError as e:
        logger.warning(f"Login failed: {e}")
        _log_exception_chain(e, "Login: ")
        friendly_message = _get_friendly_error_message(e)
        raise HTTPException(status_code=401, detail=friendly_message) from e
    except httpx.HTTPStatusError as e:
        # Handle HTTP errors from Homebox based on status code
        _log_exception_chain(e, "Login: ")
        if e.response.status_code == 401:
            logger.warning("Login failed: Invalid credentials (401)")
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password. Please check your credentials.",
            ) from e
        elif e.response.status_code == 403:
            logger.warning("Login failed: Forbidden (403)")
            raise HTTPException(
                status_code=403, detail="Access forbidden. Please check your credentials."
            ) from e
        elif e.response.status_code >= 500:
            logger.error(f"Login failed: Homebox server error ({e.response.status_code})")
            raise HTTPException(
                status_code=502,
                detail=f"Homebox server error (HTTP {e.response.status_code}). "
                "Please try again later.",
            ) from e
        else:
            logger.warning(f"Login failed: HTTP {e.response.status_code}")
            friendly_message = _get_friendly_error_message(e)
            raise HTTPException(status_code=401, detail=friendly_message) from e
    except Exception as e:
        # Unexpected errors should surface as 500, not 401
        # This prevents hiding server-side issues (serialization, dependency failures, etc.)
        logger.error(f"Login failed with unexpected error: {e}")
        logger.debug(f"Login: Full traceback:\n{traceback.format_exc()}")
        _log_exception_chain(e, "Login: ")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during login. "
            "Please try again or contact support.",
        ) from e


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

    try:
        response = await client.client.get(
            f"{client.base_url}/users/refresh",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code == 401:
            logger.info("Token refresh failed: token expired or invalid")
            raise HTTPException(
                status_code=401,
                detail="Token expired, please re-login",
            )

        if not response.is_success:
            logger.error(f"Token refresh failed with status {response.status_code}")
            raise HTTPException(
                status_code=502,
                detail="Failed to refresh token",
            )

        data = response.json()
        logger.info("Token refresh successful")
        return LoginResponse(
            token=data.get("token"),
            expires_at=data.get("expiresAt", ""),
        )
    except httpx.TimeoutException as e:
        logger.error("Token refresh timed out")
        raise HTTPException(
            status_code=503,
            detail="Token refresh timed out. Please try again.",
        ) from e
    except httpx.NetworkError as e:
        logger.error(f"Token refresh network error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot reach token refresh service. Please check your connection.",
        ) from e
    except HTTPException:
        # Re-raise HTTPExceptions we created above
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Token refresh failed due to an unexpected error.",
        ) from e








