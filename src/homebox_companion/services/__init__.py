"""Services for Homebox Companion.

This module contains service classes that implement business logic:
- StateManager: CSV-backed crash recovery and session state management
- GPUDetector: Hardware GPU detection for model selection
- OllamaManager: Ollama lifecycle management
"""

from __future__ import annotations

from .gpu_detector import GPUDetector, GPUInfo, GPUVendor, detect_gpu
from .ollama_manager import OllamaManager, OllamaMode, OllamaStatus
from .state_manager import ImageState, StateManager

__all__ = [
    # State management
    "StateManager",
    "ImageState",
    # GPU detection
    "GPUDetector",
    "GPUInfo",
    "GPUVendor",
    "detect_gpu",
    # Ollama management
    "OllamaManager",
    "OllamaMode",
    "OllamaStatus",
]
