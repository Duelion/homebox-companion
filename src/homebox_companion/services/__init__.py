"""Services for Homebox Companion.

This module contains service classes that implement business logic:
- StateManager: CSV-backed crash recovery and session state management
"""

from __future__ import annotations

from .state_manager import ImageState, StateManager

__all__ = ["StateManager", "ImageState"]
