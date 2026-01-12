"""Native Ollama provider for local AI processing.

This module provides a client for interacting with the Ollama API,
supporting both vision models for image analysis and text completion.

Usage:
    provider = OllamaProvider(base_url="http://localhost:11434", model="minicpm-v")

    # Check availability
    if await provider.is_available():
        # Analyze an image
        result = await provider.analyze_image(image_path, prompt)

    # List available models
    models = await provider.list_models()

    # Pull a model
    await provider.pull_model("minicpm-v")
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from loguru import logger


class OllamaError(Exception):
    """Base exception for Ollama-related errors."""

    pass


class OllamaConnectionError(OllamaError):
    """Raised when connection to Ollama fails."""

    pass


class OllamaModelError(OllamaError):
    """Raised when there's an issue with the model."""

    pass


class OllamaProvider:
    """Native Ollama provider for local AI processing.

    Provides a client for interacting with the Ollama API, including:
    - Connection testing and health checks
    - Model listing and pulling
    - Vision-based image analysis
    - Streaming completions

    Attributes:
        base_url: Base URL of the Ollama server
        model: Default model to use for completions
        timeout: Request timeout in seconds
    """

    # Default extraction prompt for device labels
    DEFAULT_EXTRACTION_PROMPT = """Analyze this image of a device label and extract information.
Return ONLY valid JSON with these fields (omit if not visible):

{
  "name": "Product name or description",
  "manufacturer": "Brand/manufacturer name",
  "model_number": "Model or part number",
  "serial_number": "Serial number",
  "mac_address": "MAC address if visible",
  "fcc_id": "FCC ID if visible",
  "quantity": 1,
  "notes": "Any other relevant text"
}

Be precise - only include what you can clearly read."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "minicpm-v",
        timeout: float = 120.0,
    ):
        """Initialize the Ollama provider.

        Args:
            base_url: Base URL of the Ollama server (default: localhost:11434)
            model: Default model to use (default: minicpm-v)
            timeout: Request timeout in seconds (default: 120)
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "OllamaProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    # =========================================================================
    # Health & Status
    # =========================================================================

    async def is_available(self) -> bool:
        """Check if Ollama is running and the configured model is available.

        Returns:
            True if Ollama is running and model is available.
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                return False

            models = response.json().get("models", [])
            return any(m["name"].startswith(self.model) for m in models)
        except Exception as e:
            logger.debug(f"Ollama availability check failed: {e}")
            return False

    async def is_running(self) -> bool:
        """Check if Ollama server is running (regardless of models).

        Returns:
            True if Ollama server is responding.
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def test_connection(self, test_inference: bool = False) -> dict[str, Any]:
        """Test connection to Ollama and return status details.

        Args:
            test_inference: If True, also run a small inference test to verify
                           the model can respond within the configured timeout.

        Returns:
            Dict with connection status, model availability, and available models.
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                return {
                    "status": "error",
                    "message": f"Ollama returned status {response.status_code}",
                    "connected": False,
                }

            data = response.json()
            models = data.get("models", [])
            model_names = [m["name"] for m in models]
            model_available = any(m["name"].startswith(self.model) for m in models)

            result = {
                "status": "connected",
                "connected": True,
                "url": self.base_url,
                "model": self.model,
                "model_available": model_available,
                "available_models": model_names,
            }

            # If model is available and inference test requested, try a completion
            if model_available and test_inference:
                try:
                    logger.debug(f"Running inference test with {self.model} (timeout: {self.timeout}s)")
                    test_response = await self.complete(
                        prompt="Respond with only the word 'OK'",
                        system="You are a test assistant. Respond only with 'OK'.",
                    )
                    result["inference_tested"] = True
                    result["inference_success"] = True
                    result["inference_response"] = test_response[:50] if test_response else "OK"
                except httpx.TimeoutException:
                    result["inference_tested"] = True
                    result["inference_success"] = False
                    result["inference_error"] = f"Model timed out after {self.timeout}s. Try increasing the timeout."
                except Exception as e:
                    result["inference_tested"] = True
                    result["inference_success"] = False
                    result["inference_error"] = str(e)

            return result

        except httpx.ConnectError:
            return {
                "status": "error",
                "message": f"Cannot connect to Ollama at {self.base_url}",
                "connected": False,
            }
        except httpx.TimeoutException:
            return {
                "status": "error",
                "message": f"Connection to Ollama timed out",
                "connected": False,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "connected": False,
            }

    # =========================================================================
    # Model Management
    # =========================================================================

    async def list_models(self) -> list[dict[str, Any]]:
        """List all available models.

        Returns:
            List of model info dictionaries.
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            if response.status_code != 200:
                logger.warning(f"Failed to list models: status {response.status_code}")
                return []

            return response.json().get("models", [])
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def pull_model(
        self,
        model: str | None = None,
        stream: bool = True,
    ) -> AsyncIterator[dict[str, Any]] | dict[str, Any]:
        """Pull a model from Ollama registry.

        Args:
            model: Model to pull (default: self.model)
            stream: If True, yield progress updates

        Returns:
            If stream=True: AsyncIterator of progress dicts
            If stream=False: Final status dict
        """
        model = model or self.model
        logger.info(f"Pulling Ollama model: {model}")

        try:
            if stream:
                return self._pull_model_stream(model)
            else:
                # Non-streaming pull (can take a while)
                response = await self.client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model, "stream": False},
                    timeout=600.0,  # Models can take a while
                )
                response.raise_for_status()
                return {"status": "success", "model": model}

        except httpx.HTTPStatusError as e:
            logger.error(f"Model pull failed: {e}")
            return {"status": "error", "error": str(e)}
        except Exception as e:
            logger.error(f"Model pull failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _pull_model_stream(self, model: str) -> AsyncIterator[dict[str, Any]]:
        """Stream model pull progress."""
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/pull",
            json={"name": model, "stream": True},
            timeout=600.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass

    async def delete_model(self, model: str) -> dict[str, Any]:
        """Delete a model.

        Args:
            model: Model to delete

        Returns:
            Status dict
        """
        try:
            response = await self.client.delete(
                f"{self.base_url}/api/delete",
                json={"name": model},
            )
            if response.status_code == 200:
                return {"status": "success", "model": model}
            else:
                return {"status": "error", "message": f"Status {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def model_info(self, model: str | None = None) -> dict[str, Any] | None:
        """Get information about a specific model.

        Args:
            model: Model name (default: self.model)

        Returns:
            Model info dict or None if not found.
        """
        model = model or self.model
        try:
            response = await self.client.post(
                f"{self.base_url}/api/show",
                json={"name": model},
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.debug(f"Failed to get model info: {e}")
            return None

    # =========================================================================
    # Inference
    # =========================================================================

    async def analyze_image(
        self,
        image_path: str | Path,
        prompt: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Analyze a device label image and extract information.

        Args:
            image_path: Path to the image file
            prompt: Custom prompt (default: extraction prompt)
            model: Model to use (default: self.model)

        Returns:
            Dict with extracted fields, or error information.

        Raises:
            OllamaConnectionError: If connection to Ollama fails
            OllamaModelError: If model is not available
        """
        model = model or self.model
        prompt = prompt or self.DEFAULT_EXTRACTION_PROMPT

        # Read and encode image
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode()

        logger.debug(f"Analyzing image with Ollama ({model}): {image_path.name}")

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "format": "json",
                },
            )

            response.raise_for_status()
            result = response.json()
            raw_text = result.get("response", "")

            # Parse JSON response
            try:
                parsed = json.loads(raw_text)
                logger.debug(f"Ollama extraction successful: {list(parsed.keys())}")
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"Ollama returned non-JSON response: {e}")
                return {
                    "raw_response": raw_text,
                    "parse_error": True,
                    "error": str(e),
                }

        except httpx.ConnectError as e:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise OllamaModelError(
                    f"Model '{model}' not found. Run: ollama pull {model}"
                ) from e
            raise OllamaError(f"Ollama request failed: {e}") from e
        except Exception as e:
            raise OllamaError(f"Ollama analysis failed: {e}") from e

    async def analyze_image_bytes(
        self,
        image_bytes: bytes,
        prompt: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Analyze image from bytes.

        Args:
            image_bytes: Raw image bytes
            prompt: Custom prompt (default: extraction prompt)
            model: Model to use (default: self.model)

        Returns:
            Dict with extracted fields.
        """
        model = model or self.model
        prompt = prompt or self.DEFAULT_EXTRACTION_PROMPT
        image_b64 = base64.b64encode(image_bytes).decode()

        logger.debug(f"Analyzing image bytes with Ollama ({model})")

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "format": "json",
                },
            )

            response.raise_for_status()
            result = response.json()
            raw_text = result.get("response", "")

            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                return {"raw_response": raw_text, "parse_error": True}

        except Exception as e:
            raise OllamaError(f"Ollama analysis failed: {e}") from e

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        system: str | None = None,
        format_json: bool = False,
    ) -> str:
        """Generate a text completion.

        Args:
            prompt: The prompt text
            model: Model to use (default: self.model)
            system: Optional system prompt
            format_json: If True, request JSON output

        Returns:
            Generated text
        """
        model = model or self.model

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        if system:
            payload["system"] = system

        if format_json:
            payload["format"] = "json"

        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            raise OllamaError(f"Completion failed: {e}") from e

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        format_json: bool = False,
    ) -> dict[str, Any]:
        """Chat completion with message history.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (default: self.model)
            format_json: If True, request JSON output

        Returns:
            Response dict with 'message' key
        """
        model = model or self.model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        if format_json:
            payload["format"] = "json"

        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise OllamaError(f"Chat completion failed: {e}") from e
