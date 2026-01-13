"""Field preferences API routes."""

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel

from homebox_companion.core.field_preferences import (
    FieldPreferences,
    get_defaults,
    load_field_preferences,
    reset_field_preferences,
    save_field_preferences,
)
from homebox_companion.tools.vision.prompts import build_detection_system_prompt

from ..dependencies import require_auth

# Router with authentication required for all routes
# Uses FastAPI's dependencies parameter to apply auth at router level
router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/settings/field-preferences", response_model=FieldPreferences)
async def get_field_preferences() -> FieldPreferences:
    """Get current field preferences.

    Returns the user-defined instructions for each AI output field.
    Authentication is enforced at router level.
    """
    return load_field_preferences()


@router.put("/settings/field-preferences", response_model=FieldPreferences)
async def update_field_preferences(
    prefs: FieldPreferences,
) -> FieldPreferences:
    """Update field preferences.

    Saves the user-defined instructions for AI output fields.
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

    return prefs


@router.delete("/settings/field-preferences", response_model=FieldPreferences)
async def delete_field_preferences() -> FieldPreferences:
    """Reset field preferences to defaults.

    Clears all custom field instructions and restores default behavior.
    Authentication is enforced at router level.
    """
    logger.info("Resetting field preferences to defaults")
    prefs = reset_field_preferences()
    logger.info("Field preferences reset complete")

    return prefs


# EffectiveDefaultsResponse reuses FieldPreferences


@router.get("/settings/effective-defaults", response_model=FieldPreferences)
async def get_effective_defaults() -> FieldPreferences:
    """Get effective defaults for field preferences.

    Returns the resolved defaults (env vars + hardcoded fallbacks).
    Used by the UI to display what defaults will be used when a field is reset.
    Authentication is enforced at router level.
    """
    return get_defaults()


# PromptPreviewRequest reuses FieldPreferences for consistency


class PromptPreviewResponse(BaseModel):
    """Response model for prompt preview."""

    prompt: str


@router.post("/settings/prompt-preview", response_model=PromptPreviewResponse)
async def get_prompt_preview(
    prefs: FieldPreferences,
) -> PromptPreviewResponse:
    """Generate a preview of the AI system prompt.

    Shows what the LLM will see based on the provided field preferences.
    Uses example labels for illustration purposes.
    Authentication is enforced at router level.
    """
    # Use provided preferences directly - they already have defaults baked in
    field_prefs = prefs.get_effective_customizations()
    output_language = prefs.output_language
    # None means "use default English" for the prompt builder
    if output_language.lower() == "english":
        output_language = None

    # Example labels for preview
    example_labels = [
        {"id": "abc123", "name": "Electronics"},
        {"id": "def456", "name": "Tools"},
        {"id": "ghi789", "name": "Supplies"},
    ]

    # Generate the system prompt
    prompt = build_detection_system_prompt(
        labels=example_labels,
        single_item=False,
        extract_extended_fields=True,
        field_preferences=field_prefs,
        output_language=output_language,
    )

    return PromptPreviewResponse(prompt=prompt)
