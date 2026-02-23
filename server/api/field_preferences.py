"""Field preferences API routes."""

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel

from homebox_companion.core.field_preferences import (
    FieldPreferences,
    get_defaults,
    load_user_overrides,
    reset_field_preferences,
    save_field_preferences,
)
from homebox_companion.core.persistent_settings import CustomFieldDefinition
from homebox_companion.tools.vision.prompts import build_detection_system_prompt

from ..dependencies import require_auth

# Router with authentication required for all routes
# Uses FastAPI's dependencies parameter to apply auth at router level
router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/settings/field-preferences")
async def get_field_preferences() -> dict[str, str | None]:
    """Get user-overridden field preferences (sparse data).

    Returns only fields the user has explicitly saved. Fields without
    an override are returned as None, allowing the UI to show empty
    inputs with placeholder text for defaults.

    Authentication is enforced at router level.
    """
    return load_user_overrides()


@router.put("/settings/field-preferences")
async def update_field_preferences(
    prefs: FieldPreferences,
) -> dict[str, str | None]:
    """Update field preferences.

    Saves the user-defined instructions for AI output fields.
    Returns only the user overrides (sparse data).
    Authentication is enforced at router level.
    """
    logger.info("Updating field preferences")
    save_field_preferences(prefs)

    # Log which fields differ from defaults
    defaults = get_defaults()
    customized_fields = [field for field in prefs.model_fields if getattr(prefs, field) != getattr(defaults, field)]

    logger.info(f"Field preferences saved: {len(customized_fields)} fields customized")
    if customized_fields:
        logger.debug(f"Customized fields: {', '.join(customized_fields)}")

    return load_user_overrides()


@router.delete("/settings/field-preferences")
async def delete_field_preferences() -> dict[str, str | None]:
    """Reset field preferences to defaults.

    Clears all custom field instructions and restores default behavior.
    Returns empty overrides (all None values).
    Authentication is enforced at router level.
    """
    logger.info("Resetting field preferences to defaults")
    reset_field_preferences()
    logger.info("Field preferences reset complete")

    return load_user_overrides()


# EffectiveDefaultsResponse reuses FieldPreferences


@router.get("/settings/effective-defaults", response_model=FieldPreferences)
async def get_effective_defaults() -> FieldPreferences:
    """Get effective defaults for field preferences.

    Returns the resolved defaults (env vars + hardcoded fallbacks).
    Used by the UI to display what defaults will be used when a field is reset.
    Authentication is enforced at router level.
    """
    return get_defaults()


class PromptPreviewRequest(BaseModel):
    """Request model for prompt preview.

    Contains all data needed to render the prompt — the endpoint
    does NOT reach into PersistentSettings. The frontend sends
    the current editor state directly.
    """

    field_preferences: FieldPreferences
    custom_fields: list[CustomFieldDefinition] = []


class PromptPreviewResponse(BaseModel):
    """Response model for prompt preview."""

    prompt: str


@router.post("/settings/prompt-preview", response_model=PromptPreviewResponse)
async def get_prompt_preview(
    body: PromptPreviewRequest,
) -> PromptPreviewResponse:
    """Generate a preview of the AI system prompt.

    Shows what the LLM will see based on the provided field preferences
    and custom field definitions. All inputs come from the request body —
    no server-side settings are read.

    Authentication is enforced at router level.
    """
    prefs = body.field_preferences

    # Use provided preferences directly - they already have defaults baked in
    field_prefs = prefs.get_effective_customizations()
    output_language = prefs.output_language
    # None means "use default English" for the prompt builder
    if output_language.lower() == "english":
        output_language = None

    # Example tags for preview
    example_tags = [
        {"id": "abc123", "name": "Electronics"},
        {"id": "def456", "name": "Tools"},
        {"id": "ghi789", "name": "Supplies"},
    ]

    # Generate the system prompt
    prompt = build_detection_system_prompt(
        tags=example_tags,
        single_item=False,
        extract_extended_fields=True,
        field_preferences=field_prefs,
        output_language=output_language,
        custom_fields=body.custom_fields,
    )

    return PromptPreviewResponse(prompt=prompt)
