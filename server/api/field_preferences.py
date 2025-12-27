"""Field preferences API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from loguru import logger

from homebox_companion import HomeboxClient
from homebox_companion.core.field_preferences import (
    FieldPreferences,
    get_defaults,
    load_field_preferences,
    reset_field_preferences,
    save_field_preferences,
)
from homebox_companion.tools.vision.prompts import build_detection_system_prompt

from ..dependencies import get_client, get_token

router = APIRouter()


@router.get("/settings/field-preferences", response_model=FieldPreferences)
async def get_field_preferences(
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> FieldPreferences:
    """Get current field preferences.

    Returns the user-defined instructions for each AI output field.
    Requires authentication.
    """
    # Token/client validated by Depends - no additional action needed
    _ = token, client  # Silence unused variable warnings
    return load_field_preferences()


@router.put("/settings/field-preferences", response_model=FieldPreferences)
async def update_field_preferences(
    prefs: FieldPreferences,
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> FieldPreferences:
    """Update field preferences.

    Saves the user-defined instructions for AI output fields.
    Requires authentication.
    """
    # Token/client validated by Depends - no additional action needed
    _ = token, client  # Silence unused variable warnings

    logger.info("Updating field preferences")
    save_field_preferences(prefs)

    # Log which fields differ from defaults
    defaults = get_defaults()
    customized_fields = [
        field
        for field in prefs.model_fields
        if getattr(prefs, field) != getattr(defaults, field)
    ]

    logger.info(f"Field preferences saved: {len(customized_fields)} fields customized")
    if customized_fields:
        logger.debug(f"Customized fields: {', '.join(customized_fields)}")

    return prefs


@router.delete("/settings/field-preferences", response_model=FieldPreferences)
async def delete_field_preferences(
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> FieldPreferences:
    """Reset field preferences to defaults.

    Clears all custom field instructions and restores default behavior.
    Requires authentication.
    """
    # Token/client validated by Depends - no additional action needed
    _ = token, client  # Silence unused variable warnings

    logger.info("Resetting field preferences to defaults")
    prefs = reset_field_preferences()
    logger.info("Field preferences reset complete")

    return prefs


# EffectiveDefaultsResponse reuses FieldPreferences


@router.get("/settings/effective-defaults", response_model=FieldPreferences)
async def get_effective_defaults(
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> FieldPreferences:
    """Get effective defaults for field preferences.

    Returns the resolved defaults (env vars + hardcoded fallbacks).
    Used by the UI to display what defaults will be used when a field is reset.
    Requires authentication.
    """
    # Token/client validated by Depends - no additional action needed
    _ = token, client  # Silence unused variable warnings
    return get_defaults()


# PromptPreviewRequest reuses FieldPreferences for consistency


class PromptPreviewResponse(BaseModel):
    """Response model for prompt preview."""

    prompt: str


@router.post("/settings/prompt-preview", response_model=PromptPreviewResponse)
async def get_prompt_preview(
    prefs: FieldPreferences,
    token: Annotated[str, Depends(get_token)] = None,
    client: Annotated[HomeboxClient, Depends(get_client)] = None,
) -> PromptPreviewResponse:
    """Generate a preview of the AI system prompt.

    Shows what the LLM will see based on the provided field preferences.
    Uses example labels for illustration purposes.
    """
    # Token/client validated by Depends - no additional action needed
    _ = token, client  # Silence unused variable warnings

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
