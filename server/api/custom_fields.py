"""Custom field definitions CRUD API routes."""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from homebox_companion.core.persistent_settings import (
    CustomFieldDefinition,
    get_settings,
    save_settings,
)
from homebox_companion.tools.vision.models import DetectedItem

from ..dependencies import require_auth

# Router with authentication required for all routes
router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/settings/custom-fields")
async def get_custom_fields() -> list[CustomFieldDefinition]:
    """Get all custom field definitions."""
    persistent = get_settings()
    return persistent.custom_fields


@router.put("/settings/custom-fields")
async def update_custom_fields(
    fields: list[CustomFieldDefinition],
) -> list[CustomFieldDefinition]:
    """Replace all custom field definitions.

    Expects the full list of custom field definitions. This is an
    idempotent replace operation — the frontend sends the complete
    desired state.
    """
    # Dynamic vision models inherit DetectedItem and BaseModel. A custom key
    # must not shadow either a field/alias or a model method.
    names = [f.name for f in fields]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="Custom field names must be unique")
    field_keys = [f.field_key for f in fields]
    prompt_keys = [f.prompt_key for f in fields]
    if len(field_keys) != len(set(field_keys)) or len(prompt_keys) != len(set(prompt_keys)):
        raise HTTPException(status_code=400, detail="Custom field keys must be unique")
    reserved = set(dir(BaseModel)) | set(dir(DetectedItem)) | set(DetectedItem.model_fields)
    reserved.update(field.alias for field in DetectedItem.model_fields.values() if field.alias)
    if any(
        field_key in reserved or prompt_key in reserved
        for field_key, prompt_key in zip(field_keys, prompt_keys, strict=True)
    ):
        raise HTTPException(status_code=400, detail="Custom field name conflicts with an item field")

    persistent = get_settings()
    persistent.custom_fields = fields
    save_settings(persistent)

    logger.info(f"Custom fields updated: {len(fields)} definitions")
    for f in fields:
        logger.debug(f"  {f.name}: {f.ai_instruction}")

    return persistent.custom_fields


@router.delete("/settings/custom-fields/{field_name}")
async def delete_custom_field(field_name: str) -> list[CustomFieldDefinition]:
    """Delete a single custom field definition by name."""
    persistent = get_settings()
    original_count = len(persistent.custom_fields)
    persistent.custom_fields = [f for f in persistent.custom_fields if f.name != field_name]

    if len(persistent.custom_fields) == original_count:
        raise HTTPException(status_code=404, detail=f"Custom field '{field_name}' not found")

    save_settings(persistent)
    logger.info(f"Custom field '{field_name}' deleted")

    return persistent.custom_fields
