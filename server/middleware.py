"""Request middleware for Homebox Companion API."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from loguru import logger
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# ContextVar for request ID - accessible throughout the request lifecycle
# Default "-" handles cases outside request context (startup, background tasks)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDMiddleware:
    """Pure ASGI middleware for X-Request-ID header correlation.

    This implementation avoids BaseHTTPMiddleware which can cause issues
    with streaming responses (SSE, websockets).

    - Uses incoming X-Request-ID if provided (for distributed tracing)
    - Generates 12-char hex ID if not provided (collision-safe for monitoring)
    - Sets ContextVar for log correlation via logger.contextualize()
    - Returns X-Request-ID in response headers
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            # Pass through non-HTTP requests unchanged
            await self.app(scope, receive, send)
            return

        # Extract request ID from headers or generate new one
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode() or uuid.uuid4().hex[:12]

        # Set ContextVar for access throughout the request
        token = request_id_var.set(request_id)

        # Store on scope for access in routes if needed
        scope["state"] = scope.get("state", {})
        scope["state"]["request_id"] = request_id

        async def send_wrapper(message: Message) -> None:
            """Inject X-Request-ID into response headers."""
            if message["type"] == "http.response.start":
                # Create new headers list to avoid mutating the original message
                headers = MutableHeaders(raw=list(message.get("headers", [])))
                headers["X-Request-ID"] = request_id
                # Create new message dict rather than mutating in-place
                message = {**message, "headers": headers.raw}
            await send(message)

        # Bind request_id to all logs within this request context
        with logger.contextualize(request_id=request_id):
            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                # Reset the ContextVar
                request_id_var.reset(token)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware for security headers.

    Adds common security headers to all HTTP responses:
    - X-Content-Type-Options: nosniff - Prevents MIME-sniffing attacks
    - X-Frame-Options: DENY - Prevents clickjacking (legacy)
    - Content-Security-Policy: frame-ancestors 'none' - Modern clickjacking protection
    - Referrer-Policy: strict-origin-when-cross-origin - Limits referrer leakage
    - Permissions-Policy: Restricts browser features

    Note: HSTS is intentionally not included here as it forces HTTPS and is
    typically handled at the reverse proxy layer. Adding it at the app level
    could cause issues for users running locally over HTTP.
    """

    # Headers to add to all responses
    SECURITY_HEADERS: list[tuple[str, str]] = [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Content-Security-Policy", "frame-ancestors 'none'"),
        ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ("Permissions-Policy", "camera=(self), microphone=(self), geolocation=(self)"),
    ]

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            """Inject security headers into response headers."""
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=list(message.get("headers", [])))
                for name, value in self.SECURITY_HEADERS:
                    headers[name] = value
                message = {**message, "headers": headers.raw}
            await send(message)

        await self.app(scope, receive, send_wrapper)
