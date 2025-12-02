"""Authentication schemas for the Homebox Vision API."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login credentials for Homebox authentication."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Response after successful authentication."""

    token: str
    message: str = "Login successful"
