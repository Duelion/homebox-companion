"""Credential redaction for newly emitted log entries.

Registered secrets stay masked for the process lifetime, including after a profile
is changed. Never read settings files or acquire their locks from a logging sink.
"""

from __future__ import annotations

import json
import re
from threading import RLock

from pydantic import SecretStr

_secrets: set[str] = set()
_lock = RLock()
_REDACTED = "[REDACTED]"
_CREDENTIAL_FIELD = re.compile(
    r"""(?i)((?:["']?(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|authorization|"""
    r"""client[_ -]?secret|secret|token|cookie|set-cookie|x-companion-log-token)["']?)\s*(?::|=|provided:)\s*)"""
    r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}"']+)"""
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_KEY = re.compile(r"\b(?:sk-|hb_|hf_)[A-Za-z0-9_-]{8,}(?:\.{3}|\*+)?")


def register_secrets(*values: str | SecretStr | None) -> None:
    """Remember configured secrets without retaining their surrounding settings."""
    with _lock:
        for value in values:
            raw = value.get_secret_value() if isinstance(value, SecretStr) else value
            if raw and raw.strip():
                _secrets.add(raw)
                _secrets.add(raw.strip())


def _redact_text(text: str) -> str:
    from .config import settings

    register_secrets(settings.llm_api_key, settings.openai_api_key, settings.homebox_api_key)
    with _lock:
        secrets = tuple(_secrets)

    def replace_field(match: re.Match[str]) -> str:
        value = match.group(2)
        quote = value[0] if value.startswith(('"', "'")) else ""
        return f"{match.group(1)}{quote}{_REDACTED}{quote}"

    # Handle complete auth schemes before field masking could remove "Bearer".
    # Mask labels before configured short values can alter a credential label.
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _CREDENTIAL_FIELD.sub(replace_field, text)
    text = _KEY.sub(_REDACTED, text)
    prefix_groups: dict[str, list[str]] = {}
    for secret in sorted(secrets, key=len, reverse=True):
        if len(secret) >= 8:
            text = text.replace(secret, _REDACTED)
            prefix_groups.setdefault(secret[:8], []).append(secret)
    # Providers sometimes echo only the first 100+ chars of a long key. Keys
    # can share a prefix, so consume the longest match across every candidate.
    for prefix, candidates in prefix_groups.items():
        start = text.find(prefix)
        while start != -1:
            length = 8
            for candidate in candidates:
                matched = 8
                while (
                    matched < len(candidate)
                    and start + matched < len(text)
                    and text[start + matched] == candidate[matched]
                ):
                    matched += 1
                length = max(length, matched)
            text = text[:start] + _REDACTED + text[start + length :]
            start = text.find(prefix, start + len(_REDACTED))

    for secret in secrets:
        if len(secret) < 8:
            text = text.replace(secret, _REDACTED)

    return text


def redact_sensitive(text: str) -> str:
    """Mask credentials while preserving the structure of JSON log entries."""
    if text.lstrip().startswith(("{", "[")):
        try:
            parsed = json.loads(text)
        except ValueError, RecursionError:
            pass
        else:

            def redact_value(value: object) -> object:
                if isinstance(value, str):
                    return _redact_text(value)
                if isinstance(value, list):
                    return [redact_value(item) for item in value]
                if isinstance(value, dict):
                    return {
                        key: (_REDACTED if _CREDENTIAL_FIELD.search(f"{key}=value") else redact_value(item))
                        for key, item in value.items()
                    }
                return value

            return json.dumps(redact_value(parsed), ensure_ascii=False) + ("\n" if text.endswith("\n") else "")
    return _redact_text(text)
