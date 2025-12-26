"""Request middleware for Homebox Companion API."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ContextVar for request ID - accessible throughout the request lifecycle
# Default "-" handles cases outside request context (startup, background tasks)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add X-Request-ID header for request correlation.

    - Uses incoming X-Request-ID if provided (for distributed tracing)
    - Generates 12-char hex ID if not provided (collision-safe for monitoring)
    - Sets ContextVar for log correlation via logger.contextualize()
    - Returns X-Request-ID in response headers
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use existing header or generate new ID (12 chars is collision-safe)
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request_id_var.set(request_id)

        # Store on request.state for access in routes if needed
        request.state.request_id = request_id

        # Import here to avoid circular imports at module load
        from loguru import logger

        # Bind request_id to all logs within this request context
        with logger.contextualize(request_id=request_id):
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response
