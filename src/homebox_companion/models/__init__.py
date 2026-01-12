"""Data models for Homebox Companion.

This module contains Pydantic models for:
- Session state and metadata
- Image processing state
- Extraction results
"""

from __future__ import annotations

from .session import ExtractionResult, SessionMeta, SessionStatus

__all__ = ["SessionMeta", "SessionStatus", "ExtractionResult"]
