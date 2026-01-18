"""LLM Profiles API routes.

CRUD operations for LLM model profiles with connection testing.
API keys are never sent to the frontend - only `has_api_key: bool` is exposed.
"""

import litellm
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, SecretStr

from homebox_companion.core.persistent_settings import (
    ModelProfile,
    ProfileStatus,
    Settings,
    clear_settings_cache,
    load_settings,
    save_settings,
)

from ..dependencies import require_auth

router = APIRouter(dependencies=[Depends(require_auth)])


# ============================================================================
# Response Models (safe for frontend - no secrets)
# ============================================================================


class ProfileResponse(BaseModel):
    """Profile data safe for frontend display."""

    name: str
    model: str
    has_api_key: bool
    api_base: str | None
    status: str


class ProfileListResponse(BaseModel):
    """List of profiles for frontend."""

    profiles: list[ProfileResponse]


class ProfileCreateRequest(BaseModel):
    """Request to create a new profile."""

    name: str
    model: str
    api_key: str | None = None
    api_base: str | None = None
    status: str = "off"


class ProfileUpdateRequest(BaseModel):
    """Request to update an existing profile.

    For api_key:
    - None/missing = keep existing key unchanged
    - "sk-xxx" = set new key
    """

    new_name: str | None = None
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None
    status: str | None = None


class TestConnectionRequest(BaseModel):
    """Request to test a profile connection."""

    # Optional override for testing before saving
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None


class TestConnectionResponse(BaseModel):
    """Response from connection test."""

    success: bool
    message: str
    model_info: dict | None = None


# ============================================================================
# Helper Functions
# ============================================================================


def _profile_to_response(profile: ModelProfile) -> ProfileResponse:
    """Convert internal profile to safe frontend response."""
    return ProfileResponse(
        name=profile.name,
        model=profile.model,
        has_api_key=profile.api_key is not None,
        api_base=profile.api_base,
        status=profile.status.value,
    )


def _find_profile(settings: Settings, name: str) -> tuple[int, ModelProfile]:
    """Find profile by name, raise 404 if not found."""
    for i, p in enumerate(settings.llm_profiles):
        if p.name == name:
            return i, p
    raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/llm/profiles", response_model=ProfileListResponse)
async def list_profiles() -> ProfileListResponse:
    """List all LLM profiles (API keys masked)."""
    clear_settings_cache()
    settings = load_settings()

    profiles = [_profile_to_response(p) for p in settings.llm_profiles]
    return ProfileListResponse(profiles=profiles)


@router.post("/llm/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(request: ProfileCreateRequest) -> ProfileResponse:
    """Create a new LLM profile."""
    clear_settings_cache()
    settings = load_settings()

    # Check for duplicate name
    for p in settings.llm_profiles:
        if p.name == request.name:
            raise HTTPException(status_code=409, detail=f"Profile '{request.name}' already exists")

    # If this is the first profile, make it active
    status = ProfileStatus(request.status)
    if not settings.llm_profiles:
        status = ProfileStatus.PRIMARY
        logger.info("First profile created, setting as primary")

    new_profile = ModelProfile(
        name=request.name,
        model=request.model,
        api_key=SecretStr(request.api_key) if request.api_key else None,
        api_base=request.api_base,
        status=status,
    )

    settings.llm_profiles.append(new_profile)
    save_settings(settings)
    logger.info(f"Created LLM profile: {request.name}")

    return _profile_to_response(new_profile)


@router.put("/llm/profiles/{name}", response_model=ProfileResponse)
async def update_profile(name: str, request: ProfileUpdateRequest) -> ProfileResponse:
    """Update an existing LLM profile."""
    clear_settings_cache()
    settings = load_settings()

    _, profile = _find_profile(settings, name)

    # Handle renaming
    if request.new_name is not None and request.new_name != name:
        # Check for duplicate name
        for p in settings.llm_profiles:
            if p.name == request.new_name:
                raise HTTPException(status_code=409, detail=f"Profile '{request.new_name}' already exists")
        profile.name = request.new_name
        logger.info(f"Renamed LLM profile: {name} -> {request.new_name}")

    # Update fields if provided
    if request.model is not None:
        profile.model = request.model

    if request.api_base is not None:
        profile.api_base = request.api_base if request.api_base else None

    # Handle api_key specially
    if request.api_key is not None:
        if request.api_key == "":
            profile.api_key = None  # Clear the key
        else:
            profile.api_key = SecretStr(request.api_key)

    if request.status is not None:
        new_status = ProfileStatus(request.status)

        # If setting to active, deactivate others
        if new_status == ProfileStatus.PRIMARY:
            for p in settings.llm_profiles:
                if p.status == ProfileStatus.PRIMARY:
                    p.status = ProfileStatus.OFF

        # If setting to fallback, remove other fallbacks
        if new_status == ProfileStatus.FALLBACK:
            for p in settings.llm_profiles:
                if p.status == ProfileStatus.FALLBACK:
                    p.status = ProfileStatus.OFF

        profile.status = new_status

    save_settings(settings)
    logger.info(f"Updated LLM profile: {profile.name}")

    return _profile_to_response(profile)


@router.delete("/llm/profiles/{name}", status_code=204)
async def delete_profile(name: str) -> None:
    """Delete an LLM profile."""
    clear_settings_cache()
    settings = load_settings()

    idx, profile = _find_profile(settings, name)
    was_active = profile.status == ProfileStatus.PRIMARY

    # Remove the profile by index
    del settings.llm_profiles[idx]

    # If deleted the active profile, activate the first remaining one
    if was_active and settings.llm_profiles:
        settings.llm_profiles[0].status = ProfileStatus.PRIMARY
        logger.info(f"Activated '{settings.llm_profiles[0].name}' after deleting primary profile")

    save_settings(settings)
    logger.info(f"Deleted LLM profile: {name}")


@router.post("/llm/profiles/{name}/activate", response_model=ProfileResponse)
async def activate_profile(name: str) -> ProfileResponse:
    """Set a profile as the active one."""
    clear_settings_cache()
    settings = load_settings()

    _, profile = _find_profile(settings, name)

    # Deactivate current primary
    for p in settings.llm_profiles:
        if p.status == ProfileStatus.PRIMARY:
            p.status = ProfileStatus.OFF

    # Activate the target profile (already in the list, mutated in-place)
    profile.status = ProfileStatus.PRIMARY
    save_settings(settings)
    logger.info(f"Activated LLM profile: {name}")

    return _profile_to_response(profile)


@router.post("/llm/profiles/{name}/test", response_model=TestConnectionResponse)
async def test_profile_connection(name: str, request: TestConnectionRequest | None = None) -> TestConnectionResponse:
    """Test connection to an LLM profile.

    Optionally override settings for testing before saving.
    """

    clear_settings_cache()
    settings = load_settings()

    _, profile = _find_profile(settings, name)

    # Use overrides if provided, otherwise use saved values
    model = request.model if request and request.model else profile.model
    api_key = (
        request.api_key
        if request and request.api_key
        else (profile.api_key.get_secret_value() if profile.api_key else None)
    )
    api_base = request.api_base if request and request.api_base else profile.api_base

    try:
        # Simple completion test
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "Say 'connection successful' in exactly two words."}],
            api_key=api_key,
            api_base=api_base,
            max_tokens=10,
            timeout=15,
        )

        model_info = {
            "model": response.model,
            "provider": getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown"),
        }

        return TestConnectionResponse(
            success=True,
            message="Connection successful",
            model_info=model_info,
        )

    except litellm.AuthenticationError as e:
        logger.warning(f"Auth error testing profile {name}: {e}")
        return TestConnectionResponse(
            success=False,
            message="Authentication failed. Check your API key.",
        )

    except litellm.NotFoundError as e:
        logger.warning(f"Model not found testing profile {name}: {e}")
        return TestConnectionResponse(
            success=False,
            message=f"Model '{model}' not found. Check the model name.",
        )

    except litellm.APIConnectionError as e:
        logger.warning(f"Connection error testing profile {name}: {e}")
        return TestConnectionResponse(
            success=False,
            message=f"Could not connect to API. Check api_base URL: {api_base or 'default'}",
        )

    except Exception as e:
        logger.error(f"Error testing profile {name}: {e}")
        return TestConnectionResponse(
            success=False,
            message=f"Connection test failed: {e!s}",
        )
