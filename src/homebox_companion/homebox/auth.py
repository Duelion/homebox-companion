"""Credential resolution for request-bound Homebox access."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import SecretStr


class HomeboxAuthKind(StrEnum):
    LEGACY = "legacy"
    API_KEY = "api_key"


@dataclass(frozen=True, slots=True)
class HomeboxAccess:
    """Immutable outbound credential and request scope."""

    credential: SecretStr
    kind: HomeboxAuthKind
    identity_scope: str
    group_id: str | None = None


class CredentialProvider(Protocol):
    def resolve(self, authorization: str | None, group_id: str | None = None) -> HomeboxAccess: ...


def _bearer(authorization: str | None) -> str:
    if not authorization:
        raise ValueError("Authorization header required")
    scheme, separator, value = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not value.strip():
        raise ValueError("Invalid authorization format")
    return value.strip()


class LegacySessionProvider:
    """Resolve a browser-supplied Homebox session."""

    def resolve(self, authorization: str | None, group_id: str | None = None) -> HomeboxAccess:
        token = _bearer(authorization)
        # The digest is only an in-memory cache scope and is never exposed.
        scope = hashlib.sha256(token.encode()).hexdigest()
        return HomeboxAccess(SecretStr(token), HomeboxAuthKind.LEGACY, scope, group_id)


class ConfiguredAPIKeyProvider:
    """Always resolve the server-configured key, ignoring browser credentials."""

    def __init__(self, key: SecretStr):
        raw = key.get_secret_value().strip()
        if not raw or any(char.isspace() for char in raw) or not raw.startswith("hb_"):
            raise ValueError("HBC_HOMEBOX_API_KEY must be a raw Homebox key beginning with 'hb_'")
        self._key = SecretStr(raw)

    def resolve(self, authorization: str | None, group_id: str | None = None) -> HomeboxAccess:
        _ = authorization
        return HomeboxAccess(self._key, HomeboxAuthKind.API_KEY, "configured-api-key", group_id)
