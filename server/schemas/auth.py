"""Authentication request/response schemas."""

from typing import Literal

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login credentials."""

    username: str
    password: str


class ApiKeyLoginRequest(BaseModel):
    """Homebox API key login."""

    api_key: str


class LoginResponse(BaseModel):
    """Login response with token."""

    token: str
    expires_at: str
    auth_type: Literal["jwt", "api_key"] = "jwt"
    email: str | None = None
    message: str = "Login successful"
