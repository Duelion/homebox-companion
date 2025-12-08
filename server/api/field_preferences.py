"""Field preferences API routes."""

from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel

from homebox_companion.core.field_preferences import (
    FieldPreferences,
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
    )
    save_field_preferences(prefs)

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
    prefs = reset_field_preferences()
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
    """
    get_token(authorization)  # Validate auth

    # Build field preferences dict from request (only non-null values)
    field_prefs = {}
    if request.name:
        field_prefs["name"] = request.name
    if request.description:
        field_prefs["description"] = request.description
    if request.quantity:
        field_prefs["quantity"] = request.quantity
    if request.manufacturer:
        field_prefs["manufacturer"] = request.manufacturer
    if request.model_number:
        field_prefs["model_number"] = request.model_number
    if request.serial_number:
        field_prefs["serial_number"] = request.serial_number
    if request.purchase_price:
        field_prefs["purchase_price"] = request.purchase_price
    if request.purchase_from:
        field_prefs["purchase_from"] = request.purchase_from
    if request.notes:
        field_prefs["notes"] = request.notes

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
        field_preferences=field_prefs if field_prefs else None,
        output_language=request.output_language,
    )

    return PromptPreviewResponse(prompt=prompt)

