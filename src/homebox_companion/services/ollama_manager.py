"""Ollama lifecycle manager for internal and external Ollama instances.

This module manages:
- Detection of internal vs external Ollama
- Starting/stopping embedded Ollama (when running in Docker with embedded mode)
- Model availability checking and pulling
- Automatic fallback to cloud providers

Usage:
    manager = OllamaManager()
    await manager.initialize()

    if await manager.is_ready():
        result = await manager.analyze_image(image_path)
    else:
        # Fall back to cloud provider
        ...
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from ..providers.ollama import OllamaProvider, OllamaError
from .gpu_detector import GPUInfo, detect_gpu


class OllamaMode(str, Enum):
    """Ollama operation mode."""

    DISABLED = "disabled"  # Ollama not used
    INTERNAL = "internal"  # Embedded Ollama (in Docker container)
    EXTERNAL = "external"  # External Ollama server


@dataclass
class OllamaStatus:
    """Current status of Ollama integration."""

    mode: OllamaMode
    connected: bool = False
    url: str = ""
    current_model: str = ""
    model_ready: bool = False
    available_models: list[str] | None = None
    gpu: GPUInfo | None = None
    internal_running: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "mode": self.mode.value,
            "connected": self.connected,
            "url": self.url,
            "current_model": self.current_model,
            "model_ready": self.model_ready,
            "available_models": self.available_models or [],
            "gpu": self.gpu.to_dict() if self.gpu else None,
            "internal_running": self.internal_running,
            "error": self.error,
        }


class OllamaManager:
    """Manage Ollama lifecycle and provide unified interface.

    Handles:
    - Internal Ollama (embedded in Docker container)
    - External Ollama (user-provided server)
    - Automatic mode detection based on configuration
    - Model management (list, pull, check availability)

    Attributes:
        mode: Current operation mode
        provider: OllamaProvider instance for API calls
        gpu_info: Detected GPU information
    """

    # Default configuration
    DEFAULT_URL = "http://localhost:11434"
    DEFAULT_MODEL = "minicpm-v"

    # Recommended models by VRAM
    RECOMMENDED_MODELS = {
        "48gb+": "llama3.2-vision:90b",
        "8gb+": "llama3.2-vision:11b",
        "6gb+": "minicpm-v",
        "4gb+": "granite3.2-vision",
        "3gb+": "moondream",
        "cpu": "moondream",
    }

    def __init__(
        self,
        use_ollama: bool = False,
        internal: bool = False,
        url: str | None = None,
        model: str | None = None,
        fallback_enabled: bool = True,
        timeout: float = 120.0,
    ):
        """Initialize the Ollama manager.

        Args:
            use_ollama: Whether to use Ollama at all
            internal: Use embedded/internal Ollama
            url: External Ollama URL (ignored if internal=True)
            model: Model to use
            fallback_enabled: Whether to fall back to cloud if Ollama fails
            timeout: Request timeout in seconds
        """
        self.use_ollama = use_ollama
        self.internal = internal
        self.url = url or self.DEFAULT_URL
        self.model = model or self.DEFAULT_MODEL
        self.fallback_enabled = fallback_enabled
        self.timeout = timeout

        # Determine mode
        if not use_ollama:
            self.mode = OllamaMode.DISABLED
        elif internal:
            self.mode = OllamaMode.INTERNAL
        else:
            self.mode = OllamaMode.EXTERNAL

        # Provider and state
        self._provider: OllamaProvider | None = None
        self._gpu_info: GPUInfo | None = None
        self._initialized = False
        self._internal_process: subprocess.Popen | None = None

    @property
    def provider(self) -> OllamaProvider | None:
        """Get the Ollama provider instance."""
        return self._provider

    @property
    def gpu_info(self) -> GPUInfo | None:
        """Get detected GPU information."""
        return self._gpu_info

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def initialize(self) -> None:
        """Initialize the Ollama manager.

        - Detects GPU
        - Starts internal Ollama if configured
        - Creates provider and tests connection
        """
        if self._initialized:
            return

        logger.info(f"Initializing Ollama manager (mode: {self.mode.value})")

        # Detect GPU
        self._gpu_info = detect_gpu()

        if self.mode == OllamaMode.DISABLED:
            logger.info("Ollama disabled, skipping initialization")
            self._initialized = True
            return

        # For internal mode, attempt to start Ollama
        if self.mode == OllamaMode.INTERNAL:
            await self._start_internal()

        # Create provider
        self._provider = OllamaProvider(
            base_url=self.url,
            model=self.model,
            timeout=self.timeout,
        )

        # Test connection
        status = await self._provider.test_connection()
        if status["connected"]:
            logger.info(f"Ollama connected at {self.url}")
            if not status.get("model_available"):
                logger.warning(
                    f"Model '{self.model}' not available. "
                    f"Available: {status.get('available_models', [])}"
                )
        else:
            logger.warning(f"Ollama not available: {status.get('message')}")

        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown the Ollama manager."""
        logger.info("Shutting down Ollama manager")

        # Close provider
        if self._provider:
            await self._provider.close()
            self._provider = None

        # Stop internal Ollama
        if self._internal_process:
            await self._stop_internal()

        self._initialized = False

    async def _start_internal(self) -> bool:
        """Start the internal/embedded Ollama server.

        Returns:
            True if Ollama was started or is already running.
        """
        # Check if ollama binary exists
        ollama_path = shutil.which("ollama")
        if not ollama_path:
            logger.warning("Ollama binary not found in PATH")
            return False

        # Check if already running
        test_provider = OllamaProvider(base_url=self.url)
        try:
            if await test_provider.is_running():
                logger.info("Internal Ollama already running")
                await test_provider.close()
                return True
        except Exception:
            pass
        finally:
            await test_provider.close()

        # Start Ollama serve
        logger.info(f"Starting internal Ollama server at {self.url}")
        try:
            self._internal_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for server to be ready
            for _ in range(30):  # 30 second timeout
                await asyncio.sleep(1)
                test_provider = OllamaProvider(base_url=self.url)
                try:
                    if await test_provider.is_running():
                        logger.info("Internal Ollama server started")
                        await test_provider.close()
                        return True
                except Exception:
                    pass
                finally:
                    await test_provider.close()

            logger.error("Timeout waiting for internal Ollama to start")
            return False

        except Exception as e:
            logger.error(f"Failed to start internal Ollama: {e}")
            return False

    async def _stop_internal(self) -> None:
        """Stop the internal Ollama server."""
        if self._internal_process:
            logger.info("Stopping internal Ollama server")
            self._internal_process.terminate()
            try:
                self._internal_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._internal_process.kill()
            self._internal_process = None

    # =========================================================================
    # Status
    # =========================================================================

    async def get_status(self) -> OllamaStatus:
        """Get current Ollama status.

        Returns:
            OllamaStatus with current state information.
        """
        status = OllamaStatus(
            mode=self.mode,
            url=self.url,
            current_model=self.model,
            gpu=self._gpu_info,
            internal_running=self._internal_process is not None,
        )

        if self.mode == OllamaMode.DISABLED or not self._provider:
            return status

        # Test connection
        conn_status = await self._provider.test_connection()
        status.connected = conn_status.get("connected", False)
        status.model_ready = conn_status.get("model_available", False)
        status.available_models = conn_status.get("available_models", [])

        if not status.connected:
            status.error = conn_status.get("message")

        return status

    async def is_ready(self) -> bool:
        """Check if Ollama is ready to process requests.

        Returns:
            True if connected and model is available.
        """
        if self.mode == OllamaMode.DISABLED or not self._provider:
            return False

        return await self._provider.is_available()

    # =========================================================================
    # Model Management
    # =========================================================================

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models.

        Returns:
            List of model information dicts.
        """
        if not self._provider:
            return []

        return await self._provider.list_models()

    async def pull_model(self, model: str | None = None) -> dict[str, Any]:
        """Pull a model.

        Args:
            model: Model to pull (default: configured model)

        Returns:
            Status dict
        """
        if not self._provider:
            return {"status": "error", "error": "Ollama not initialized"}

        model = model or self.model
        logger.info(f"Pulling model: {model}")

        try:
            result = await self._provider.pull_model(model, stream=False)
            return result
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def ensure_model(self) -> bool:
        """Ensure the configured model is available, pulling if needed.

        Returns:
            True if model is available after check/pull.
        """
        if not self._provider:
            return False

        # Check if model exists
        if await self._provider.is_available():
            return True

        # Try to pull
        logger.info(f"Model '{self.model}' not found, attempting to pull...")
        result = await self.pull_model()

        return result.get("status") == "success"

    def get_recommended_model(self) -> str:
        """Get recommended model based on detected GPU.

        Returns:
            Model name recommendation.
        """
        if self._gpu_info:
            return self._gpu_info.recommended_model
        return self.RECOMMENDED_MODELS["cpu"]

    # =========================================================================
    # Inference
    # =========================================================================

    async def analyze_image(
        self,
        image_path: str | Path,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Analyze an image using Ollama.

        Args:
            image_path: Path to the image
            prompt: Custom prompt (optional)

        Returns:
            Extraction result dict

        Raises:
            OllamaError: If Ollama fails and fallback is disabled
            RuntimeError: If Ollama is not initialized
        """
        if not self._provider:
            raise RuntimeError("Ollama not initialized")

        try:
            return await self._provider.analyze_image(image_path, prompt)
        except OllamaError as e:
            if self.fallback_enabled:
                logger.warning(f"Ollama failed, fallback enabled: {e}")
                raise  # Let caller handle fallback
            raise

    async def analyze_image_bytes(
        self,
        image_bytes: bytes,
        prompt: str | None = None,
    ) -> dict[str, Any]:
        """Analyze image from bytes.

        Args:
            image_bytes: Raw image bytes
            prompt: Custom prompt (optional)

        Returns:
            Extraction result dict
        """
        if not self._provider:
            raise RuntimeError("Ollama not initialized")

        return await self._provider.analyze_image_bytes(image_bytes, prompt)


# =========================================================================
# Factory function
# =========================================================================


def create_ollama_manager_from_settings() -> OllamaManager:
    """Create an OllamaManager from current settings.

    Reads configuration from environment variables:
    - HBC_USE_OLLAMA: Enable Ollama
    - HBC_OLLAMA_INTERNAL: Use internal Ollama
    - HBC_OLLAMA_URL: External Ollama URL
    - HBC_OLLAMA_MODEL: Model to use
    - HBC_FALLBACK_TO_CLOUD: Enable fallback

    Returns:
        Configured OllamaManager instance
    """
    from ..core.config import settings

    return OllamaManager(
        use_ollama=getattr(settings, "use_ollama", False),
        internal=getattr(settings, "ollama_internal", False),
        url=getattr(settings, "ollama_url", OllamaManager.DEFAULT_URL),
        model=getattr(settings, "ollama_model", OllamaManager.DEFAULT_MODEL),
        fallback_enabled=getattr(settings, "fallback_to_cloud", True),
        timeout=settings.llm_timeout,
    )


# Module-level singleton
_manager: OllamaManager | None = None


async def get_ollama_manager() -> OllamaManager:
    """Get or create the singleton OllamaManager.

    Returns:
        Initialized OllamaManager instance.
    """
    global _manager
    if _manager is None:
        _manager = create_ollama_manager_from_settings()
        await _manager.initialize()
    return _manager
