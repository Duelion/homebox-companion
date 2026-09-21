"""Homebox bootstrap and connection status endpoints."""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from homebox_companion import HomeboxAuthError, HomeboxGateway

from ..dependencies import _default_group_id, get_gateway

router = APIRouter()


class ConnectionResponse(BaseModel):
    connected: bool
    context_id: str
    user_id: str
    default_group_id: str | None


@router.get("/homebox/connection", response_model=ConnectionResponse)
async def connection_status(
    request: Request,
    gateway: Annotated[HomeboxGateway, Depends(get_gateway)],
) -> ConnectionResponse:
    """Validate selected credentials and return safe bootstrap identity."""
    try:
        user = await gateway.get_current_user()
    except HomeboxAuthError as exc:
        if request.app.state.settings.auth_mode == "api_key":
            exc.status_code = 502
            exc.error_code = "HOMEBOX_API_KEY_REJECTED"
            exc.user_message = "The configured Homebox API key was rejected."
        raise

    user_id = user["id"]
    credential_scope = hashlib.sha256(
        gateway.access.credential.get_secret_value().encode()
    ).hexdigest()
    app_settings = request.app.state.settings
    deployment = app_settings.api_url.casefold().rstrip("/")
    context_id = hashlib.sha256(f"{deployment}|{app_settings.auth_mode}|{user_id}".encode()).hexdigest()[:32]
    default_group = _default_group_id(user)
    request.app.state.homebox_identities[credential_scope] = (user_id, default_group)
    return ConnectionResponse(
        connected=True,
        context_id=context_id,
        user_id=user_id,
        default_group_id=default_group,
    )
