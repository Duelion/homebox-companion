"""Request middleware for Homebox Companion API."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from loguru import logger
from starlette.datastructures import Headers, MutableHeaders
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from homebox_companion.core.config import Settings
from homebox_companion.homebox.auth import LegacySessionProvider

# ContextVar for request ID - accessible throughout the request lifecycle
# Default "-" handles cases outside request context (startup, background tasks)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestBodyLimitMiddleware:
    """Limit bytes before body parsers can buffer or spool an unbounded request."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.max_bytes = settings.max_request_size_mb * 1024 * 1024

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        multipart = headers.get("content-type", "").split(";", 1)[0].strip().lower() == "multipart/form-data"
        if multipart and scope.get("path", "").startswith("/api/") and self.settings.auth_mode == "legacy":
            # Every multipart API route requires a session. Reject absent/malformed
            # credentials before reading files; route dependencies still validate it.
            try:
                LegacySessionProvider().resolve(headers.get("authorization"))
            except ValueError as exc:
                await JSONResponse({"detail": str(exc)}, status_code=401)(scope, receive, send)
                return

        rejection = JSONResponse(
            {"detail": f"Request too large. Maximum total size is {self.settings.max_request_size_mb}MB"},
            status_code=413,
        )
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = -1
            if declared_size < 0:
                await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
                return
            if declared_size > self.max_bytes:
                await rejection(scope, receive, send)
                return

        consumed = 0
        exceeded = False
        rejection_sent = False

        async def limited_receive() -> Message:
            nonlocal consumed, exceeded
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_bytes:
                    exceeded = True
                    # MultiPartException also closes partially spooled files in
                    # Starlette versions that only clean up parser exceptions.
                    raise MultiPartException("Request body exceeds configured limit")
            return message

        async def limited_send(message: Message) -> None:
            nonlocal rejection_sent
            if exceeded:
                # Starlette maps parser exceptions to 400; return the actual
                # cause (413) after the parser has unwound and closed its files.
                if not rejection_sent:
                    rejection_sent = True
                    await rejection(scope, receive, send)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except MultiPartException:
            if not exceeded:
                raise
            if not rejection_sent:
                await rejection(scope, receive, send)


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


class APIKeyBrowserGuardMiddleware:
    """Require an explicit non-simple header on unsafe API-key-mode requests."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or self.settings.auth_mode != "api_key"
            or scope.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}
            or not scope.get("path", "").startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return

        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        if headers.get("x-companion-request") != "1":
            await self._reject(send)
            return

        origin = headers.get("origin")
        if origin:
            host = headers.get("host", "")
            same_origin = origin.rstrip("/") in {f"http://{host}", f"https://{host}"}
            configured = self.settings.browser_origins_list
            allowed = origin in configured
            if not same_origin and not allowed:
                await self._reject(send)
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = b'{"detail":"Unsafe API-key request rejected","code":"REQUEST_GUARD_REQUIRED"}'
        await send({"type": "http.response.start", "status": 403, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})


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
