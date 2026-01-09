"""FastAPI dependencies for dependency injection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

import httpx
from fastapi import Depends, Header, HTTPException, UploadFile
from loguru import logger

from homebox_companion import HomeboxAuthError, HomeboxClient, settings

if TYPE_CHECKING:
    from homebox_companion.chat.session import ChatSession
    from homebox_companion.chat.store import SessionStoreProtocol
    from homebox_companion.mcp.executor import ToolExecutor

from homebox_companion.core.field_preferences import FieldPreferences, load_field_preferences
from homebox_companion.core.ai_config import load_ai_config, AIProvider
from homebox_companion.services.duplicate_detector import DuplicateDetector


class ClientHolder:
    """Manages the lifecycle of the shared HomeboxClient instance.

    This class provides explicit lifecycle management for the HTTP client,
    making it easier to configure for testing and multi-worker deployments.

    Usage:
        # In app lifespan:
        client = HomeboxClient(base_url=settings.api_url)
        client_holder.set(client)
        yield
        await client_holder.close()

        # In tests:
        client_holder.set(mock_client)
        # ... run tests ...
        client_holder.reset()

    Note:
        In multi-worker deployments (e.g., uvicorn --workers N), each worker
        maintains its own ClientHolder instance. This is the expected behavior
        for async HTTP clients, as httpx.AsyncClient is not thread-safe.
    """

    def __init__(self) -> None:
        self._client: HomeboxClient | None = None

    def set(self, client: HomeboxClient) -> None:
        """Set the shared client instance.

        Args:
            client: The HomeboxClient instance to use.
        """
        self._client = client

    def get(self) -> HomeboxClient:
        """Get the shared client instance.

        Returns:
            The shared HomeboxClient instance.

        Raises:
            HTTPException: If the client has not been initialized.
        """
        if self._client is None:
            raise HTTPException(status_code=500, detail="Client not initialized")
        return self._client

    async def close(self) -> None:
        """Close the client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def reset(self) -> None:
        """Reset the holder without closing (for testing).

        Use this in tests to reset state between test cases.
        For normal shutdown, use close() instead.
        """
        self._client = None


# Singleton holder instance - each worker gets its own
client_holder = ClientHolder()


class DuplicateDetectorHolder:
    """Manages the shared DuplicateDetector instance.

    The DuplicateDetector maintains a persistent index of serial numbers
    for duplicate detection. It should be shared across requests to benefit
    from caching and incremental updates.
    """

    def __init__(self) -> None:
        self._detector: DuplicateDetector | None = None

    def get_or_create(self, client: HomeboxClient) -> DuplicateDetector:
        """Get the shared detector instance, creating if needed.

        Args:
            client: The HomeboxClient to use for API calls.

        Returns:
            The shared DuplicateDetector instance.
        """
        if self._detector is None:
            self._detector = DuplicateDetector(client)
            logger.debug("Created new DuplicateDetector instance")
        return self._detector

    def get(self) -> DuplicateDetector | None:
        """Get the detector if initialized, or None."""
        return self._detector

    def reset(self) -> None:
        """Reset the holder (for testing)."""
        self._detector = None


# Singleton holder for duplicate detector
duplicate_detector_holder = DuplicateDetectorHolder()


class SessionStoreHolder:
    """Manages the lifecycle of the shared session store.

    Similar to ClientHolder, this provides explicit lifecycle management
    for the session store, enabling testing and future backend swaps.

    Usage:
        # In app lifespan:
        session_store_holder.set(MemorySessionStore())
        yield
        # No cleanup needed for memory store

        # In tests:
        session_store_holder.set(mock_store)
        # ... run tests ...
        session_store_holder.reset()
    """

    def __init__(self) -> None:
        self._store: SessionStoreProtocol | None = None

    def set(self, store: SessionStoreProtocol) -> None:
        """Set the shared store instance.

        Args:
            store: The session store instance to use.
        """
        self._store = store

    def get(self) -> SessionStoreProtocol:
        """Get the shared store instance, creating default if needed.

        Returns:
            The shared session store instance.
        """
        if self._store is None:
            from homebox_companion.chat.store import MemorySessionStore

            self._store = MemorySessionStore()
            logger.debug("Created default MemorySessionStore")
        return self._store

    def reset(self) -> None:
        """Reset the holder (for testing).

        Use this in tests to reset state between test cases.
        """
        self._store = None


# Singleton session store holder
session_store_holder = SessionStoreHolder()


class ToolExecutorHolder:
    """Manages the shared ToolExecutor instance.

    This makes the ToolExecutor a singleton, ensuring that schema caching
    is effective across requests rather than being recreated per-request.

    The holder tracks the client reference to ensure the executor is
    recreated if the client changes (important for testing).

    Usage:
        # Get executor (auto-creates if needed):
        executor = tool_executor_holder.get(client)

        # In tests:
        tool_executor_holder.reset()
    """

    def __init__(self) -> None:
        self._executor: ToolExecutor | None = None
        self._client_id: int | None = None  # Track client identity

    def get(self, client: HomeboxClient) -> ToolExecutor:
        """Get or create the shared executor instance.

        If the client reference has changed (e.g., during testing),
        the executor is recreated with the new client.

        Args:
            client: HomeboxClient for tool execution.

        Returns:
            The shared ToolExecutor instance.
        """
        from homebox_companion.mcp.executor import ToolExecutor

        current_client_id = id(client)

        # Recreate executor if client has changed
        if self._executor is None or self._client_id != current_client_id:
            if self._executor is not None:
                logger.debug("Client changed, recreating ToolExecutor")
            self._executor = ToolExecutor(client)
            self._client_id = current_client_id
            logger.debug("Created shared ToolExecutor instance")

        return self._executor

    def reset(self) -> None:
        """Reset the holder (for testing).

        Use this in tests to reset state between test cases.
        """
        self._executor = None
        self._client_id = None


# Singleton tool executor holder
tool_executor_holder = ToolExecutorHolder()


# =============================================================================
# CORE DEPENDENCIES (defined first so they can be used in Depends())
# =============================================================================



def get_client() -> HomeboxClient:
    """Get the shared Homebox client.

    This is a FastAPI dependency that returns the shared client instance.
    Can be overridden in tests using app.dependency_overrides[get_client].
    """
    return client_holder.get()


def get_duplicate_detector(
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> DuplicateDetector:
    """Get the shared DuplicateDetector instance.

    This is a FastAPI dependency that returns the shared detector instance,
    creating it if needed. The detector maintains a persistent index of
    serial numbers for duplicate detection.
    """
    return duplicate_detector_holder.get_or_create(client)


def get_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    return authorization[7:]


# =============================================================================
# COMPOSITE DEPENDENCIES (depend on core dependencies above)
# =============================================================================


def get_executor(
    client: Annotated[HomeboxClient, Depends(get_client)],
) -> ToolExecutor:
    """Get the shared ToolExecutor.

    This is a FastAPI dependency that returns the shared executor instance.
    Can be overridden in tests using app.dependency_overrides[get_executor].
    """
    return tool_executor_holder.get(client)



def get_session(
    token: Annotated[str, Depends(get_token)],
) -> ChatSession:
    """Get the chat session for the current user.

    This is a FastAPI dependency that retrieves (or creates) the session
    for the authenticated user.

    Args:
        token: The user's auth token (from get_token dependency).

    Returns:
        The ChatSession for this user.
    """
    store = session_store_holder.get()
    return store.get(token)


def require_auth(token: Annotated[str, Depends(get_token)]) -> None:
    """Dependency that validates authentication without returning the token.

    Use this when a route needs authentication but doesn't use the token directly.
    This avoids injecting unused dependencies and makes intent clear.

    Usage:
        @router.get("/protected", dependencies=[Depends(require_auth)])
        async def protected_route() -> dict:
            return {"status": "authenticated"}
    """
    # Token validation happens in get_token; explicitly acknowledge unused param
    _ = token


@dataclass
class LLMConfig:
    """Configuration for LLM access.

    Attributes:
        api_key: The API key for the provider (may be None for Ollama/LiteLLM).
        model: The model name to use.
        provider: The provider type (ollama, openai, anthropic, litellm).
    """

    api_key: str | None
    model: str
    provider: str


def get_llm_config() -> LLMConfig:
    """Get LLM configuration from AI config or environment variables.

    This function checks the AI config file first, then falls back to
    environment variables for backward compatibility.

    Returns:
        LLMConfig with api_key, model, and provider.

    Raises:
        HTTPException: 500 if no LLM is properly configured.
    """
    # First, try to load from new AI config system
    try:
        ai_config = load_ai_config()
        active_provider = ai_config.active_provider

        if active_provider == AIProvider.OLLAMA:
            if ai_config.ollama.enabled:
                return LLMConfig(
                    api_key=None,  # Ollama doesn't need API key
                    model=ai_config.ollama.model,
                    provider="ollama",
                )
        elif active_provider == AIProvider.OPENAI:
            if ai_config.openai.enabled and ai_config.openai.api_key:
                return LLMConfig(
                    api_key=ai_config.openai.api_key.get_secret_value(),
                    model=ai_config.openai.model,
                    provider="openai",
                )
        elif active_provider == AIProvider.ANTHROPIC:
            if ai_config.anthropic.enabled and ai_config.anthropic.api_key:
                return LLMConfig(
                    api_key=ai_config.anthropic.api_key.get_secret_value(),
                    model=ai_config.anthropic.model,
                    provider="anthropic",
                )
        elif active_provider == AIProvider.LITELLM:
            if ai_config.litellm.enabled:
                # LiteLLM uses environment variable or app-provided key
                return LLMConfig(
                    api_key=settings.effective_llm_api_key,  # May be None
                    model=ai_config.litellm.model,
                    provider="litellm",
                )
    except Exception as e:
        logger.debug(f"Could not load AI config, falling back to env vars: {e}")

    # Fall back to environment variables (backward compatibility)
    if settings.effective_llm_api_key:
        return LLMConfig(
            api_key=settings.effective_llm_api_key,
            model=settings.effective_llm_model,
            provider="litellm",  # Env vars use LiteLLM
        )

    logger.error("LLM API key not configured")
    raise HTTPException(
        status_code=500,
        detail="LLM API key not configured. Configure a provider in Settings or set HBC_LLM_API_KEY.",
    )


def require_llm_configured() -> str:
    """Dependency that ensures LLM API key is configured.

    Use this as a FastAPI dependency in endpoints that require LLM access.
    The returned key can be used directly or ignored if only validation is needed.

    Returns:
        The configured LLM API key.

    Raises:
        HTTPException: 500 if LLM API key is not configured.
    """
    config = get_llm_config()
    # For providers that don't need API key (Ollama), return empty string
    return config.api_key or ""


def get_configured_llm() -> LLMConfig:
    """Dependency that returns the full LLM configuration.

    Use this when you need both the API key and model from the configured provider.

    Returns:
        LLMConfig with api_key, model, and provider.

    Raises:
        HTTPException: 500 if no LLM is properly configured.
    """
    return get_llm_config()


def get_fallback_llm_config() -> LLMConfig | None:
    """Get the fallback LLM configuration if enabled.

    Returns:
        LLMConfig for the fallback provider, or None if fallback is disabled
        or the fallback provider is not properly configured.
    """
    try:
        ai_config = load_ai_config()

        # Check if fallback is enabled
        if not ai_config.fallback_to_cloud:
            return None

        fallback_provider = ai_config.fallback_provider

        # Don't fallback to the same provider
        if fallback_provider == ai_config.active_provider:
            return None

        # Get fallback provider config
        if fallback_provider == AIProvider.OLLAMA:
            if ai_config.ollama.enabled:
                return LLMConfig(
                    api_key=None,
                    model=ai_config.ollama.model,
                    provider="ollama",
                )
        elif fallback_provider == AIProvider.OPENAI:
            if ai_config.openai.enabled and ai_config.openai.api_key:
                return LLMConfig(
                    api_key=ai_config.openai.api_key.get_secret_value(),
                    model=ai_config.openai.model,
                    provider="openai",
                )
        elif fallback_provider == AIProvider.ANTHROPIC:
            if ai_config.anthropic.enabled and ai_config.anthropic.api_key:
                return LLMConfig(
                    api_key=ai_config.anthropic.api_key.get_secret_value(),
                    model=ai_config.anthropic.model,
                    provider="anthropic",
                )
        elif fallback_provider == AIProvider.LITELLM:
            if ai_config.litellm.enabled:
                return LLMConfig(
                    api_key=settings.effective_llm_api_key,
                    model=ai_config.litellm.model,
                    provider="litellm",
                )

        return None
    except Exception as e:
        logger.debug(f"Could not load fallback config: {e}")
        return None


def get_configured_llm_with_fallback() -> tuple[LLMConfig, LLMConfig | None]:
    """Get both primary and fallback LLM configurations.

    Returns:
        Tuple of (primary_config, fallback_config).
        fallback_config is None if fallback is disabled.
    """
    primary = get_llm_config()
    fallback = get_fallback_llm_config()
    return primary, fallback


async def validate_file_size(file: UploadFile) -> bytes:
    """Read and validate file size against configured limit.

    Args:
        file: The uploaded file to validate.

    Returns:
        The file contents as bytes.

    Raises:
        HTTPException: If file exceeds size limit or is empty.
    """
    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    max_size = settings.max_upload_size_bytes
    if len(contents) > max_size:
        max_mb = settings.max_upload_size_mb
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_mb}MB",
        )

    return contents


async def validate_files_size(files: list[UploadFile]) -> list[tuple[bytes, str]]:
    """Read and validate multiple files against configured limit.

    Args:
        files: List of uploaded files to validate.

    Returns:
        List of tuples containing (file_bytes, content_type).

    Raises:
        HTTPException: If any file exceeds size limit or is empty.
    """
    results = []
    for file in files:
        contents = await validate_file_size(file)
        content_type = file.content_type or "application/octet-stream"
        results.append((contents, content_type))
    return results


async def get_labels_for_context(token: str) -> list[dict[str, str]]:
    """Fetch labels and format them for AI context.

    Args:
        token: The bearer token for authentication.

    Returns:
        List of label dicts with 'id' and 'name' keys.

    Raises:
        HomeboxAuthError: If authentication fails (re-raised to caller).
        RuntimeError: If the API returns an unexpected error (not transient).
    """
    client = get_client()
    try:
        raw_labels = await client.list_labels(token)
        return [
            {"id": str(label.get("id", "")), "name": str(label.get("name", ""))}
            for label in raw_labels
            if label.get("id") and label.get("name")
        ]
    except HomeboxAuthError:
        # Re-raise auth errors - session is invalid and caller needs to know
        logger.warning("Authentication failed while fetching labels for AI context")
        raise
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        # Transient network errors: gracefully degrade - AI can work without labels
        logger.warning(
            f"Transient network error fetching labels for AI context: {type(e).__name__}. "
            "Continuing without label suggestions.",
        )
        return []
    # Let other errors (RuntimeError from API, schema errors, etc.) propagate
    # to surface issues rather than silently degrading AI behavior


# =============================================================================
# VISION CONTEXT - Bundles all context needed for vision endpoints
# =============================================================================


@dataclass
class VisionContext:
    """Context bundle for vision AI endpoints.

    This dataclass consolidates all the common context needed by vision
    endpoints, reducing boilerplate and ensuring field preferences are
    only loaded once per request.

    Attributes:
        token: Bearer token for Homebox API authentication.
        labels: List of available labels for AI context.
        field_preferences: Custom field instructions dict, or None if no customizations.
        output_language: Configured output language, or None for default (English).
        default_label_id: ID of label to auto-add, or None.
    """

    token: str
    labels: list[dict[str, str]]
    field_preferences: dict[str, str] | None
    output_language: str | None
    default_label_id: str | None


async def get_vision_context(
    authorization: Annotated[str | None, Header()] = None,
    x_field_preferences: Annotated[str | None, Header()] = None,
) -> VisionContext:
    """FastAPI dependency that loads all vision endpoint context.

    This dependency:
    1. Extracts and validates the auth token
    2. Fetches labels for AI context
    3. Loads field preferences (from header in demo mode, or from file/env)

    Args:
        authorization: The Authorization header value.
        x_field_preferences: Optional JSON-encoded field preferences (for demo mode).

    Returns:
        VisionContext with all required data for vision endpoints.
    """
    token = get_token(authorization)

    # Load field preferences from header if provided (demo mode), otherwise from file
    if x_field_preferences:
        logger.debug("Using field preferences from X-Field-Preferences header (demo mode)")
        try:
            prefs_dict = json.loads(x_field_preferences)
            # Filter out None values - let model defaults fill in missing fields
            filtered = {k: v for k, v in prefs_dict.items() if v is not None}
            prefs = FieldPreferences.model_validate(filtered)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid field preferences in header, ignoring: {e}")
            prefs = load_field_preferences()
    else:
        prefs = load_field_preferences()

    # Determine output language (None means use default English)
    output_language = None if prefs.output_language.lower() == "english" else prefs.output_language

    return VisionContext(
        token=token,
        labels=await get_labels_for_context(token),
        # get_effective_customizations returns all prompt fields
        field_preferences=prefs.get_effective_customizations(),
        output_language=output_language,
        default_label_id=prefs.default_label_id,
    )
