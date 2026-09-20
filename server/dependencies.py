"""FastAPI dependencies for dependency injection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request, UploadFile
from loguru import logger
from pydantic import SecretStr

from homebox_companion import HomeboxAuthError, HomeboxClient, HomeboxGateway, settings
from homebox_companion.core.exceptions import HomeboxAPIError
from homebox_companion.homebox.auth import (
    ConfiguredAPIKeyProvider,
    CredentialProvider,
    HomeboxAccess,
    HomeboxAuthKind,
    LegacySessionProvider,
)

if TYPE_CHECKING:
    from homebox_companion.chat.session import ChatSession
    from homebox_companion.chat.store import SessionStoreProtocol
    from homebox_companion.core.persistent_settings import CustomFieldDefinition
    from homebox_companion.mcp.executor import ToolExecutor

from homebox_companion.core.field_preferences import FieldPreferences, load_field_preferences


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

    def reset_if(self, client: HomeboxClient) -> None:
        """Clear compatibility storage only when it still owns this client."""
        if self._client is client:
            self._client = None


# Singleton holder instance - each worker gets its own
client_holder = ClientHolder()


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

    Request-bound executors supply their own Homebox gateway while sharing
    this registry and schema cache.

    Usage:
        # Get executor (auto-creates if needed):
        executor = tool_executor_holder.get()

        # In tests:
        tool_executor_holder.reset()
    """

    def __init__(self) -> None:
        self._executor: ToolExecutor | None = None

    def get(self) -> ToolExecutor:
        """Get or create the shared executor instance.

        Returns:
            The shared ToolExecutor instance.
        """
        from homebox_companion.mcp.executor import ToolExecutor

        if self._executor is None:
            self._executor = ToolExecutor()
            logger.debug("Created shared ToolExecutor instance")

        return self._executor

    def reset(self) -> None:
        """Reset the holder (for testing).

        Use this in tests to reset state between test cases.
        """
        self._executor = None


# Singleton tool executor holder
tool_executor_holder = ToolExecutorHolder()


# =============================================================================
# CORE DEPENDENCIES (defined first so they can be used in Depends())
# =============================================================================


def get_client(request: Request) -> HomeboxClient:
    """Get the shared Homebox client.

    This is a FastAPI dependency that returns the shared client instance.
    Can be overridden in tests using app.dependency_overrides[get_client].
    """
    shared = getattr(request.app.state, "homebox_client", None) or client_holder.get()
    group_id = request.headers.get("X-Group-Id") or None
    return shared.for_group(group_id)


def get_credential_provider(request: Request) -> CredentialProvider:
    """Return the startup-selected credential provider."""
    app_settings = getattr(request.app.state, "settings", settings)
    if app_settings.homebox_api_key is not None:
        return ConfiguredAPIKeyProvider(app_settings.homebox_api_key)
    return LegacySessionProvider()


async def get_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Resolve the configured API key or the browser's legacy bearer token.

    This dependency only resolves credentials. Inventory calls validate them
    upstream; local-resource and chat dependencies explicitly verify identity
    before serving Companion-owned data.
    """
    try:
        return get_credential_provider(request).resolve(authorization).credential.get_secret_value()
    except ValueError as exc:
        if getattr(request.app.state, "settings", settings).auth_mode == "api_key":
            error = HomeboxAPIError(
                "Configured Homebox API key has invalid syntax",
                user_message="The configured Homebox API key is malformed.",
            )
            error.error_code = "HOMEBOX_API_KEY_INVALID_CONFIG"
            raise error from exc
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def get_homebox_access(
    request: Request,
    token: Annotated[str, Depends(get_token)],
    x_group_id: Annotated[str | None, Header()] = None,
) -> HomeboxAccess:
    """Resolve immutable outbound access for the current request."""
    app_settings = getattr(request.app.state, "settings", settings)
    kind = HomeboxAuthKind.API_KEY if app_settings.auth_mode == "api_key" else HomeboxAuthKind.LEGACY
    credential_scope = hashlib.sha256(token.encode()).hexdigest()
    identities = getattr(request.app.state, "homebox_identities", {})
    identity = identities.get(credential_scope)
    if identity:
        user_id, default_group_id = identity
        effective_group_id = x_group_id or default_group_id
        scope = user_id
    else:
        # Bootstrap requests have not yet verified /users/self. Keep their
        # provisional scope credential-specific; connection_status replaces it
        # with the verified user and effective default group.
        effective_group_id = x_group_id
        scope = f"unverified:{credential_scope}"
    return HomeboxAccess(SecretStr(token), kind, scope, effective_group_id)


async def get_verified_homebox_access(
    request: Request,
    token: Annotated[str, Depends(get_token)],
    client: Annotated[HomeboxClient, Depends(get_client)],
    x_group_id: Annotated[str | None, Header()] = None,
) -> HomeboxAccess:
    """Authenticate every chat request before resolving its conversation scope."""
    app_settings = getattr(request.app.state, "settings", settings)
    kind = HomeboxAuthKind.API_KEY if app_settings.auth_mode == "api_key" else HomeboxAuthKind.LEGACY
    credential_scope = hashlib.sha256(token.encode()).hexdigest()
    identities = request.app.state.homebox_identities
    # Cached identity metadata must never authorize an expired or revoked token.
    # Use the gateway so configured-key rejection retains its server-error contract.
    gateway = HomeboxGateway(client, HomeboxAccess(SecretStr(token), kind, credential_scope))
    user = await gateway.get_current_user()
    user_id = user["id"]
    default_group_id = _default_group_id(user)
    identities[credential_scope] = (user_id, default_group_id)
    return HomeboxAccess(SecretStr(token), kind, user_id, x_group_id or default_group_id)


def _default_group_id(user: dict[str, object]) -> str | None:
    """Extract Homebox's effective default group across supported response versions."""
    direct = user.get("defaultGroupId") or user.get("groupId")
    if isinstance(direct, str):
        return direct
    for key in ("defaultGroup", "group"):
        nested = user.get(key)
        if isinstance(nested, dict):
            nested_id = nested.get("id")
            if isinstance(nested_id, str):
                return nested_id
    return None


def get_gateway(
    client: Annotated[HomeboxClient, Depends(get_client)],
    access: Annotated[HomeboxAccess, Depends(get_homebox_access)],
) -> HomeboxGateway:
    """Bind transport, credential, identity scope, and group for one request."""
    return HomeboxGateway(client, access)


def get_verified_gateway(
    client: Annotated[HomeboxClient, Depends(get_client)],
    access: Annotated[HomeboxAccess, Depends(get_verified_homebox_access)],
) -> HomeboxGateway:
    """Bind a gateway only after Homebox has verified the current identity."""
    return HomeboxGateway(client, access)


# =============================================================================
# COMPOSITE DEPENDENCIES (depend on core dependencies above)
# =============================================================================


def get_executor() -> ToolExecutor:
    """Get the shared ToolExecutor.

    This is a FastAPI dependency that returns the shared executor instance.
    Can be overridden in tests using app.dependency_overrides[get_executor].
    """
    return tool_executor_holder.get()


def get_bound_executor(
    gateway: Annotated[HomeboxGateway, Depends(get_verified_gateway)],
    executor: Annotated[ToolExecutor, Depends(get_executor)],
) -> ToolExecutor:
    """Bind request access to the lifespan-shared tool registry and schema cache."""
    return executor.bind(gateway)


def get_chat_context(
    x_companion_chat_context: Annotated[str | None, Header()] = None,
) -> str:
    """Validate the browser-owned conversation identity."""
    from uuid import UUID

    if not x_companion_chat_context:
        raise HTTPException(status_code=400, detail="X-Companion-Chat-Context header required")
    try:
        return str(UUID(x_companion_chat_context))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Companion-Chat-Context header") from exc


def get_session(
    request: Request,
    chat_context: Annotated[str, Depends(get_chat_context)],
    access: Annotated[HomeboxAccess, Depends(get_verified_homebox_access)],
) -> ChatSession:
    """Get the conversation scoped to this browser and authenticated Homebox access.

    This is a FastAPI dependency that retrieves (or creates) the session
    for the deployment, auth mode, user, group and browser conversation context.

    Returns:
        The ChatSession for this conversation scope.
    """
    store = getattr(request.app.state, "session_store", None) or session_store_holder.get()
    scope = get_chat_scope(request, chat_context, access)
    return store.get(scope)


def get_chat_scope(
    request: Request,
    chat_context: Annotated[str, Depends(get_chat_context)],
    access: Annotated[HomeboxAccess, Depends(get_verified_homebox_access)],
) -> str:
    """Build a non-exported conversation scope across app, user, and group."""
    app_settings = request.app.state.settings
    return "|".join(
        (
            app_settings.api_url.casefold().rstrip("/"),
            app_settings.auth_mode,
            access.identity_scope,
            access.group_id or "",
            chat_context,
        )
    )


async def get_authenticated_user(
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> dict[str, object]:
    """Validate credentials upstream on every local-resource request.

    The bootstrap identity cache is not an authentication cache: expired or
    revoked credentials must not retain access to Companion's local resources.
    """
    return await gateway.get_current_user()


def require_auth(user: Annotated[dict[str, object], Depends(get_authenticated_user)]) -> None:
    """Require a currently authenticated Homebox identity."""
    _ = user


def require_llm_configured() -> str:
    """
    FastAPI dependency to ensure LLM is configured.

    Use this as a FastAPI dependency in endpoints that require LLM access.
    The returned key can be used directly or ignored if only validation is needed.

    Resolution order (same as LLM Router):
    1. PRIMARY profile from settings.yaml (configured via Settings UI)
    2. Environment variables (HBC_LLM_API_KEY or HBC_OPENAI_API_KEY)

    Returns:
        The configured LLM API key.

    Raises:
        HTTPException: 500 if LLM API key is not configured.
    """
    from homebox_companion.core.llm_utils import resolve_llm_credentials

    creds = resolve_llm_credentials()
    if not creds.api_key:
        logger.error("LLM API key not configured")
        raise HTTPException(
            status_code=500,
            detail="LLM API key not configured. Configure a profile in Settings or set HBC_LLM_API_KEY.",
        )
    return creds.api_key


async def validate_file_size(file: UploadFile) -> bytes:
    """Read and validate file size against configured limit.

    Args:
        file: The uploaded file to validate.

    Returns:
        The file contents as bytes.

    Raises:
        HTTPException: If file exceeds size limit or is empty.
    """
    max_size = settings.max_upload_size_bytes
    if file.size is not None and file.size > max_size:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB")
    contents = await file.read(max_size + 1)

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

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


async def get_tags_for_context(token: str, client: HomeboxClient) -> list[dict[str, str]]:
    """Fetch tags and format them for AI context.

    Args:
        token: The bearer token for authentication.

    Returns:
        List of tag dicts with 'id' and 'name' keys.

    Raises:
        HomeboxAuthError: If authentication fails (re-raised to caller).
        RuntimeError: If the API returns an unexpected error (not transient).
    """
    try:
        raw_tags = await client.list_tags(token)
        return [
            {"id": str(tag.get("id", "")), "name": str(tag.get("name", ""))}
            for tag in raw_tags
            if tag.get("id") and tag.get("name")
        ]
    except HomeboxAuthError:
        # Re-raise auth errors - session is invalid and caller needs to know
        logger.warning("Authentication failed while fetching tags for AI context")
        raise
    except (httpx.TimeoutException, httpx.NetworkError) as e:
        # Transient network errors: gracefully degrade - AI can work without tags
        logger.warning(
            f"Transient network error fetching tags for AI context: {type(e).__name__}. "
            "Continuing without tag suggestions.",
        )
        return []
    # Let other errors (RuntimeError from API, schema errors, etc.) propagate
    # to surface issues rather than silently degrading AI behavior


async def get_valid_tag_ids(gateway: HomeboxGateway) -> set[str]:
    """Fetch valid tag IDs from Homebox as a set for O(1) validation.

    Used to filter out invalid/stale tag IDs before creating items.

    Args:
        gateway: Request-bound Homebox access for the selected collection.

    Returns:
        Set of valid tag ID strings, or empty set on failure.
    """
    try:
        raw_tags = await gateway.list_tags()
        return {str(tag.get("id")) for tag in raw_tags if tag.get("id")}
    except HomeboxAuthError:
        # Re-raise auth errors - caller needs to handle
        raise
    except Exception as e:
        # Non-fatal: log and return empty set - items will be created without tags
        logger.warning(f"Failed to fetch tags for validation: {e}")
        return set()


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
        gateway: Request-bound Homebox access for inventory operations.
        tags: List of available tags for AI context.
        field_preferences: Custom field instructions dict, or None if no customizations.
        output_language: Configured output language, or None for default (English).
        default_tag_id: ID of tag to auto-add, or None.
        custom_fields: User-defined custom field definitions for AI detection.
    """

    gateway: HomeboxGateway
    tags: list[dict[str, str]]
    field_preferences: dict[str, str] | None
    output_language: str | None
    default_tag_id: str | None
    custom_fields: list[CustomFieldDefinition]


async def get_vision_context(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_field_preferences: Annotated[str | None, Header()] = None,
) -> VisionContext:
    """FastAPI dependency that loads all vision endpoint context.

    This dependency:
    1. Extracts and validates the auth token
    2. Fetches tags for AI context
    3. Loads field preferences (from header in demo mode, or from file/env)

    Args:
        authorization: The Authorization header value.
        x_field_preferences: Optional JSON-encoded field preferences (for demo mode).

    Returns:
        VisionContext with all required data for vision endpoints.
    """
    token = await get_token(request, authorization)
    app_settings = getattr(request.app.state, "settings", settings)
    kind = HomeboxAuthKind.API_KEY if app_settings.auth_mode == "api_key" else HomeboxAuthKind.LEGACY
    identity_scope = (
        "configured-api-key"
        if kind == HomeboxAuthKind.API_KEY
        else hashlib.sha256(token.encode()).hexdigest()
    )
    access = HomeboxAccess(SecretStr(token), kind, identity_scope, request.headers.get("X-Group-Id"))
    gateway = HomeboxGateway(get_client(request), access)

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

    # Load custom field definitions from persistent settings
    from homebox_companion.core.persistent_settings import get_settings

    persistent = get_settings()

    return VisionContext(
        gateway=gateway,
        tags=await gateway.list_tags(),
        # get_effective_customizations returns all prompt fields
        field_preferences=prefs.get_effective_customizations(),
        output_language=output_language,
        default_tag_id=prefs.default_tag_id,
        custom_fields=persistent.custom_fields,
    )
