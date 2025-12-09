"""Field preferences API routes."""

from typing import Annotated

from fastapi import APIRouter, Header
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

from ..dependencies import get_token

router = APIRouter()


class FieldPreferencesResponse(BaseModel):
    """Response model for field preferences."""

    output_language: str | None = None
    default_label_id: str | None = None
    name: str | None = None
    description: str | None = None
    quantity: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: str | None = None
    purchase_from: str | None = None
    notes: str | None = None
    naming_examples: str | None = None


class FieldPreferencesUpdate(BaseModel):
    """Request model for updating field preferences."""

    output_language: str | None = None
    default_label_id: str | None = None
    name: str | None = None
    description: str | None = None
    quantity: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: str | None = None
    purchase_from: str | None = None
    notes: str | None = None
    naming_examples: str | None = None


@router.get("/settings/field-preferences", response_model=FieldPreferencesResponse)
async def get_field_preferences(
    authorization: Annotated[str | None, Header()] = None,
) -> FieldPreferencesResponse:
    """Get current field preferences.

    Returns the user-defined instructions for each AI output field.
    Empty/null values indicate default behavior should be used.
    Requires authentication.
    """
    get_token(authorization)  # Validate auth
    prefs = load_field_preferences()
    return FieldPreferencesResponse(
        output_language=prefs.output_language,
        default_label_id=prefs.default_label_id,
        name=prefs.name,
        description=prefs.description,
        quantity=prefs.quantity,
        manufacturer=prefs.manufacturer,
        model_number=prefs.model_number,
        serial_number=prefs.serial_number,
        purchase_price=prefs.purchase_price,
        purchase_from=prefs.purchase_from,
        notes=prefs.notes,
        naming_examples=prefs.naming_examples,
    )


@router.put("/settings/field-preferences", response_model=FieldPreferencesResponse)
async def update_field_preferences(
    update: FieldPreferencesUpdate,
    authorization: Annotated[str | None, Header()] = None,
) -> FieldPreferencesResponse:
    """Update field preferences.

    Saves the user-defined instructions for AI output fields.
    Set a field to null or empty string to use default behavior.
    Requires authentication.
    """
    get_token(authorization)  # Validate auth
    
    logger.info("Updating field preferences")
    
    prefs = FieldPreferences(
        output_language=update.output_language,
        default_label_id=update.default_label_id,
        name=update.name,
        description=update.description,
        quantity=update.quantity,
        manufacturer=update.manufacturer,
        model_number=update.model_number,
        serial_number=update.serial_number,
        purchase_price=update.purchase_price,
        purchase_from=update.purchase_from,
        notes=update.notes,
        naming_examples=update.naming_examples,
    )
    save_field_preferences(prefs)
    
    # Log which fields were customized
    customized_fields = []
    if update.output_language:
        customized_fields.append(f"output_language={update.output_language}")
    if update.default_label_id:
        customized_fields.append("default_label_id")
    for field in ["name", "description", "quantity", "manufacturer", "model_number", 
                  "serial_number", "purchase_price", "purchase_from", "notes", "naming_examples"]:
        if getattr(update, field):
            customized_fields.append(field)
    
    logger.info(f"Field preferences saved: {len(customized_fields)} fields customized")
    logger.debug(f"Customized fields: {', '.join(customized_fields) if customized_fields else 'none'}")

    return FieldPreferencesResponse(
        output_language=prefs.output_language,
        default_label_id=prefs.default_label_id,
        name=prefs.name,
        description=prefs.description,
        quantity=prefs.quantity,
        manufacturer=prefs.manufacturer,
        model_number=prefs.model_number,
        serial_number=prefs.serial_number,
        purchase_price=prefs.purchase_price,
        purchase_from=prefs.purchase_from,
        notes=prefs.notes,
        naming_examples=prefs.naming_examples,
    )


@router.delete("/settings/field-preferences", response_model=FieldPreferencesResponse)
async def delete_field_preferences(
    authorization: Annotated[str | None, Header()] = None,
) -> FieldPreferencesResponse:
    """Reset field preferences to defaults.

    Clears all custom field instructions and restores default behavior.
    Requires authentication.
    """
    get_token(authorization)  # Validate auth
    
    logger.info("Resetting field preferences to defaults")
    prefs = reset_field_preferences()
    logger.info("Field preferences reset complete")
    
    return FieldPreferencesResponse(
        output_language=prefs.output_language,
        default_label_id=prefs.default_label_id,
        name=prefs.name,
        description=prefs.description,
        quantity=prefs.quantity,
        manufacturer=prefs.manufacturer,
        model_number=prefs.model_number,
        serial_number=prefs.serial_number,
        purchase_price=prefs.purchase_price,
        purchase_from=prefs.purchase_from,
        notes=prefs.notes,
        naming_examples=prefs.naming_examples,
    )


class EffectiveDefaultsResponse(BaseModel):
    """Response model for effective defaults (env var or hardcoded fallback)."""

    output_language: str
    default_label_id: str | None = None
    name: str
    description: str
    quantity: str
    manufacturer: str
    model_number: str
    serial_number: str
    purchase_price: str
    purchase_from: str
    notes: str
    naming_examples: str


@router.get("/settings/effective-defaults", response_model=EffectiveDefaultsResponse)
async def get_effective_defaults(
    authorization: Annotated[str | None, Header()] = None,
) -> EffectiveDefaultsResponse:
    """Get effective defaults for field preferences.

    Returns env var values (HBC_AI_*) if set, otherwise falls back to
    hardcoded defaults. Used by the UI to display what defaults will
    actually be used when a field is left empty.
    Requires authentication.
    """
    get_token(authorization)  # Validate auth

    # get_defaults() returns a FieldPreferencesDefaults instance with
    # env vars applied over hardcoded defaults - all handled by pydantic_settings
    defaults = get_defaults()

    return EffectiveDefaultsResponse(
        output_language=defaults.output_language,
        default_label_id=defaults.default_label_id,
        name=defaults.name,
        description=defaults.description,
        quantity=defaults.quantity,
        manufacturer=defaults.manufacturer,
        model_number=defaults.model_number,
        serial_number=defaults.serial_number,
        purchase_price=defaults.purchase_price,
        purchase_from=defaults.purchase_from,
        notes=defaults.notes,
        naming_examples=defaults.naming_examples,
    )


class PromptPreviewRequest(BaseModel):
    """Request model for prompt preview."""

    output_language: str | None = None
    name: str | None = None
    description: str | None = None
    quantity: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    purchase_price: str | None = None
    purchase_from: str | None = None
    notes: str | None = None
    naming_examples: str | None = None


class PromptPreviewResponse(BaseModel):
    """Response model for prompt preview."""

    prompt: str


@router.post("/settings/prompt-preview", response_model=PromptPreviewResponse)
async def get_prompt_preview(
    request: PromptPreviewRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> PromptPreviewResponse:
    """Generate a preview of the AI system prompt.

    Shows what the LLM will see based on the provided field preferences.
    Uses example labels for illustration purposes.

    When a field is empty/null in the request, uses the effective default
    (from env var or hardcoded fallback) so the preview accurately reflects
    what the AI will actually see.
    """
    get_token(authorization)  # Validate auth

    # Get effective defaults (env vars with hardcoded fallbacks)
    defaults = get_defaults()

    # Merge request values with effective defaults
    # Request value takes priority if set, otherwise use default
    field_prefs = {
        "name": request.name or defaults.name,
        "description": request.description or defaults.description,
        "quantity": request.quantity or defaults.quantity,
        "manufacturer": request.manufacturer or defaults.manufacturer,
        "model_number": request.model_number or defaults.model_number,
        "serial_number": request.serial_number or defaults.serial_number,
        "purchase_price": request.purchase_price or defaults.purchase_price,
        "purchase_from": request.purchase_from or defaults.purchase_from,
        "notes": request.notes or defaults.notes,
        "naming_examples": request.naming_examples or defaults.naming_examples,
    }

    # Output language: request value or default
    output_language = request.output_language or defaults.output_language
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
