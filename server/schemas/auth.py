"""Authentication request/response schemas."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login credentials."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with token."""

    token: str
    message: str = "Login successful"
