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

