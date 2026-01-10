"""Unit tests for Ollama provider.

Tests cover:
- Connection testing
- Model listing
- Image analysis (mocked)
- Error handling
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from homebox_companion.providers.ollama import (
    OllamaConnectionError,
    OllamaError,
    OllamaModelError,
    OllamaProvider,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock HTTP client."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.is_closed = False
    return client


@pytest.fixture
def provider(mock_client: AsyncMock) -> OllamaProvider:
    """Create an OllamaProvider instance with mocked client."""
    p = OllamaProvider(
        base_url="http://localhost:11434",
        model="minicpm-v",
        timeout=10.0,
    )
    p._client = mock_client
    return p


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock HTTP response."""
    response = MagicMock()
    response.status_code = 200
    return response


class TestOllamaProviderInit:
    """Tests for provider initialization."""

    def test_default_values(self) -> None:
        """Provider uses default values when not specified."""
        provider = OllamaProvider()

        assert provider.base_url == "http://localhost:11434"
        assert provider.model == "minicpm-v"
        assert provider.timeout == 120.0

    def test_custom_values(self) -> None:
        """Provider uses custom values when specified."""
        provider = OllamaProvider(
            base_url="http://custom:8080",
            model="llama3.2-vision:11b",
            timeout=60.0,
        )

        assert provider.base_url == "http://custom:8080"
        assert provider.model == "llama3.2-vision:11b"
        assert provider.timeout == 60.0

    def test_strips_trailing_slash(self) -> None:
        """Provider strips trailing slash from URL."""
        provider = OllamaProvider(base_url="http://localhost:11434/")

        assert provider.base_url == "http://localhost:11434"


class TestConnectionTesting:
    """Tests for connection testing methods."""

    @pytest.mark.asyncio
    async def test_is_available_success(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """is_available returns True when connected and model exists."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "minicpm-v:latest"}]
        }
        mock_client.get.return_value = mock_response

        result = await provider.is_available()

        assert result is True
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_available_model_not_found(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """is_available returns False when model not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "other-model"}]
        }
        mock_client.get.return_value = mock_response

        result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_available_connection_error(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """is_available returns False on connection error."""
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = await provider.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_running_success(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """is_running returns True when server responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response

        result = await provider.is_running()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_running_server_down(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """is_running returns False when server is down."""
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = await provider.is_running()

        assert result is False

    @pytest.mark.asyncio
    async def test_test_connection_success(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """test_connection returns detailed status on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "minicpm-v:latest"},
                {"name": "llama3.2-vision:11b"},
            ]
        }
        mock_client.get.return_value = mock_response

        result = await provider.test_connection()

        assert result["status"] == "connected"
        assert result["connected"] is True
        assert result["model"] == "minicpm-v"
        assert result["model_available"] is True
        assert "minicpm-v:latest" in result["available_models"]

    @pytest.mark.asyncio
    async def test_test_connection_failure(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """test_connection returns error details on failure."""
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = await provider.test_connection()

        assert result["status"] == "error"
        assert result["connected"] is False
        assert "Cannot connect" in result["message"]


class TestModelManagement:
    """Tests for model management methods."""

    @pytest.mark.asyncio
    async def test_list_models_success(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """list_models returns list of models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "minicpm-v:latest", "size": 5000000000},
                {"name": "llama3.2-vision:11b", "size": 7000000000},
            ]
        }
        mock_client.get.return_value = mock_response

        result = await provider.list_models()

        assert len(result) == 2
        assert result[0]["name"] == "minicpm-v:latest"

    @pytest.mark.asyncio
    async def test_list_models_empty(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """list_models returns empty list when no models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_client.get.return_value = mock_response

        result = await provider.list_models()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_models_error(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """list_models returns empty list on error."""
        mock_client.get.side_effect = Exception("Error")

        result = await provider.list_models()

        assert result == []


class TestImageAnalysis:
    """Tests for image analysis methods."""

    @pytest.fixture
    def sample_image(self, tmp_path: Path) -> Path:
        """Create a sample image file."""
        image_path = tmp_path / "test.jpg"
        image_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)
        return image_path

    @pytest.mark.asyncio
    async def test_analyze_image_success(
        self, provider: OllamaProvider, mock_client: AsyncMock, sample_image: Path
    ) -> None:
        """analyze_image returns parsed JSON on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"name": "Test Device", "manufacturer": "Acme"}'
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        result = await provider.analyze_image(sample_image)

        assert result["name"] == "Test Device"
        assert result["manufacturer"] == "Acme"

    @pytest.mark.asyncio
    async def test_analyze_image_invalid_json(
        self, provider: OllamaProvider, mock_client: AsyncMock, sample_image: Path
    ) -> None:
        """analyze_image handles non-JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Not valid JSON"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        result = await provider.analyze_image(sample_image)

        assert result["parse_error"] is True
        assert "Not valid JSON" in result["raw_response"]

    @pytest.mark.asyncio
    async def test_analyze_image_file_not_found(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """analyze_image raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            await provider.analyze_image("/nonexistent/path.jpg")

    @pytest.mark.asyncio
    async def test_analyze_image_connection_error(
        self, provider: OllamaProvider, mock_client: AsyncMock, sample_image: Path
    ) -> None:
        """analyze_image raises OllamaConnectionError on connection failure."""
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(OllamaConnectionError):
            await provider.analyze_image(sample_image)

    @pytest.mark.asyncio
    async def test_analyze_image_model_not_found(
        self, provider: OllamaProvider, mock_client: AsyncMock, sample_image: Path
    ) -> None:
        """analyze_image raises OllamaModelError for 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
        mock_client.post.return_value = mock_response

        with pytest.raises(OllamaModelError):
            await provider.analyze_image(sample_image)


class TestCompletion:
    """Tests for text completion methods."""

    @pytest.mark.asyncio
    async def test_complete_success(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """complete returns generated text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Generated text"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        result = await provider.complete("Test prompt")

        assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_complete_with_system(
        self, provider: OllamaProvider, mock_client: AsyncMock
    ) -> None:
        """complete includes system prompt in request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Result"}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        await provider.complete("Test", system="You are helpful")

        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["system"] == "You are helpful"


class TestContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Provider works as async context manager."""
        async with OllamaProvider() as provider:
            # Provider is returned from __aenter__
            assert isinstance(provider, OllamaProvider)
            # Client is created lazily, so force creation by accessing property
            _ = provider.client
            assert provider._client is not None

        # Client should be closed after context exit
        assert provider._client is None or provider._client.is_closed

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self) -> None:
        """Context manager properly closes client on exit."""
        provider = OllamaProvider()
        # Create client
        _ = provider.client
        assert provider._client is not None

        # Manually call close
        await provider.close()
        assert provider._client is None
