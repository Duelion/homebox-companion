"""Authentication request/response schemas."""

from typing import Literal

from pydantic import BaseModel, model_validator

from homebox_companion.homebox.auth_utils import is_homebox_api_key


class LoginRequest(BaseModel):
    """Login credentials — password session or Homebox API key."""

    username: str | None = None
    password: str | None = None
    api_key: str | None = None

    @model_validator(mode="after")
    def validate_credentials(self) -> LoginRequest:
        has_password_login = bool(self.username and self.password)
        has_api_key = bool(self.api_key and self.api_key.strip())

        if has_password_login and has_api_key:
            raise ValueError("Provide either username/password or api_key, not both")
        if not has_password_login and not has_api_key:
            raise ValueError("Provide username/password or api_key")
        if has_api_key and not is_homebox_api_key(self.api_key.strip()):
            raise ValueError("Invalid API key format. Homebox API keys start with hb_")
        return self


class LoginResponse(BaseModel):
    """Login response with token."""

    token: str
    expires_at: str | None = None
    auth_method: Literal["session", "api_key"]
    user_email: str | None = None
    message: str = "Login successful"
