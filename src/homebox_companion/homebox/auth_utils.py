"""Homebox authentication helpers."""

API_KEY_PREFIX = "hb_"
API_KEY_MIN_LEN = 46  # len("hb_") + 43 base64url chars


def is_homebox_api_key(token: str) -> bool:
    """Return True if token looks like a Homebox static API key."""
    return token.startswith(API_KEY_PREFIX) and len(token) >= API_KEY_MIN_LEN
