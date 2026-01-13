"""Session store abstraction for chat sessions.

This module provides a protocol-based session store that allows
future implementations (Redis, database, etc.) to replace the
in-memory default.

The MemorySessionStore is the default implementation suitable for
single-worker deployments. For multi-worker production deployments,
implement a shared backend (e.g., Redis) that satisfies the protocol.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from loguru import logger

from ..core.config import settings

if TYPE_CHECKING:
    from .session import ChatSession

# Default session TTL: 24 hours (in seconds)
_DEFAULT_SESSION_TTL = 24 * 60 * 60


@runtime_checkable
class SessionStoreProtocol(Protocol):
    """Protocol for session storage backends.

    Implementations must provide thread-safe session management.
    The token is hashed internally to avoid storing sensitive data.

    Example implementation:
        class RedisSessionStore:
            def get(self, token: str) -> ChatSession: ...
            def delete(self, token: str) -> bool: ...
            def clear_all(self) -> int: ...
    """

    def get(self, token: str) -> ChatSession:
        """Get or create a session for the given token.

        Args:
            token: The user's auth token (will be hashed internally)

        Returns:
            The ChatSession for this user
        """
        ...

    def delete(self, token: str) -> bool:
        """Delete a session.

        Args:
            token: The user's auth token

        Returns:
            True if session existed and was deleted
        """
        ...

    def clear_all(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions cleared
        """
        ...


class MemorySessionStore:
    """In-memory session store implementation with TTL-based expiration.

    This is the default implementation suitable for single-worker
    deployments. Sessions are stored in a dictionary keyed by
    a hash of the user's auth token.

    Sessions automatically expire after a configurable TTL (default 24 hours)
    to prevent memory leaks from abandoned sessions.

    Thread-safety: Uses a lock to protect concurrent access to session data.
    This is important when running with multiple threads or during tests.

    Note:
        Sessions are lost on server restart and not shared between
        workers. For production multi-worker deployments, use a
        shared backend implementation.

    Example:
        >>> store = MemorySessionStore()
        >>> session = store.get("user-token")
        >>> store.delete("user-token")
    """

    def __init__(self, session_ttl: int | None = None) -> None:
        """Initialize an empty session store.

        Args:
            session_ttl: Session TTL in seconds. Defaults to 24 hours.
        """
        # Import here to avoid circular imports
        self._sessions: dict[str, ChatSession] = {}
        self._last_access: dict[str, float] = {}  # session_key -> timestamp
        self._session_ttl = session_ttl or getattr(settings, "chat_session_ttl", _DEFAULT_SESSION_TTL)
        self._last_cleanup: float = time.time()
        # Cleanup interval: run cleanup at most once per 5 minutes
        self._cleanup_interval = 300
        # Lock for thread-safe access to session data
        self._lock = threading.Lock()

    def _get_session_key(self, token: str) -> str:
        """Generate a deterministic session key from a token.

        Args:
            token: The user's auth token

        Returns:
            A hashed session key (first 16 chars of SHA-256)
        """
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def _maybe_cleanup_expired(self) -> None:
        """Periodically clean up expired sessions.

        Only runs if enough time has passed since the last cleanup
        to avoid performance impact on every request.

        Note: Caller must hold self._lock.
        """
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        expired_keys = [key for key, last_access in self._last_access.items() if now - last_access > self._session_ttl]

        for key in expired_keys:
            del self._sessions[key]
            del self._last_access[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired sessions")

    def get(self, token: str) -> ChatSession:
        """Get or create a session for the given token.

        Args:
            token: The user's auth token

        Returns:
            The ChatSession for this user
        """
        # Import here to avoid circular imports at module load
        from .session import ChatSession

        session_key = self._get_session_key(token)
        now = time.time()

        with self._lock:
            # Periodically cleanup expired sessions
            self._maybe_cleanup_expired()

            # Check if session exists and is not expired
            if session_key in self._sessions:
                last_access = self._last_access.get(session_key, 0)
                if now - last_access > self._session_ttl:
                    # Session expired, remove it
                    del self._sessions[session_key]
                    del self._last_access[session_key]
                    logger.debug(f"Session {session_key[:8]}... expired, creating new")

            if session_key not in self._sessions:
                self._sessions[session_key] = ChatSession()
                logger.debug(f"Created new session for key {session_key[:8]}...")

            # Update last access time
            self._last_access[session_key] = now

            return self._sessions[session_key]

    def delete(self, token: str) -> bool:
        """Delete a session.

        Args:
            token: The user's auth token

        Returns:
            True if session existed and was deleted
        """
        session_key = self._get_session_key(token)
        with self._lock:
            if session_key in self._sessions:
                del self._sessions[session_key]
                self._last_access.pop(session_key, None)
                logger.info(f"Deleted session for key {session_key[:8]}...")
                return True
            return False

    def clear_all(self) -> int:
        """Clear all sessions.

        Returns:
            Number of sessions cleared
        """
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            self._last_access.clear()
            logger.info(f"Cleared all {count} sessions")
            return count

    @property
    def session_count(self) -> int:
        """Get the number of active sessions."""
        with self._lock:
            return len(self._sessions)
