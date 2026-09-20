"""Homebox API client module."""

from .auth import ConfiguredAPIKeyProvider, HomeboxAccess, HomeboxAuthKind, LegacySessionProvider
from .client import HomeboxClient, HomeboxGateway
from .models import Attachment, EntityType, Group, Item, ItemCreate, ItemUpdate, Location, Tag, has_extended_fields

__all__ = [
    "HomeboxClient",
    "HomeboxGateway",
    "ConfiguredAPIKeyProvider",
    "HomeboxAccess",
    "HomeboxAuthKind",
    "LegacySessionProvider",
    "EntityType",
    "Group",
    "Location",
    "Tag",
    "Item",
    "ItemCreate",
    "ItemUpdate",
    "Attachment",
    "has_extended_fields",
]
