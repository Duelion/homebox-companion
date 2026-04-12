"""Minimal pytest configuration for Homebox Companion tests."""

from __future__ import annotations

import http.server
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict


@pytest.fixture(scope="session", autouse=True)
def _configure_loguru_for_tests():
    """Strip all loguru sinks and keep only stderr for test runs.

    Prevents 'I/O operation on closed file' errors during pytest teardown
    caused by file sinks outliving the test process.
    """
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    yield
    logger.remove()


# ---------------------------------------------------------------------------
# Test Infrastructure Constants
# ---------------------------------------------------------------------------

HOMEBOX_IMAGE = "ghcr.io/sysadminsmedia/homebox:latest"
HOMEBOX_CONTAINER_PORT = 7745

# Demo user credentials (created automatically by HBOX_DEMO=true)
DEMO_USERNAME = "demo@example.com"
DEMO_PASSWORD = "demo"

# Test assets directory
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_homebox(base_url: str, timeout: float = 60.0, interval: float = 1.0) -> None:
    """Poll Homebox API until it responds with HTTP 200.

    Raises RuntimeError if the service doesn't become ready within *timeout* seconds.
    """
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/v1/status", timeout=3.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_err = exc
        time.sleep(interval)
    raise RuntimeError(
        f"Homebox container did not become ready within {timeout}s. Last error: {last_err}"
    )


# ---------------------------------------------------------------------------
# Mock Label Printer Server
# ---------------------------------------------------------------------------


class PrintRequest:
    """Captured request from Homebox print command."""

    __slots__ = ("method", "path", "headers", "body")

    def __init__(self, method: str, path: str, headers: dict[str, str], body: bytes) -> None:
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body


class _PrinterHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that captures POST requests from Homebox print command."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        headers = {k: v for k, v in self.headers.items()}
        self.server.captured_requests.append(  # type: ignore[attr-defined]
            PrintRequest(method="POST", path=self.path, headers=headers, body=body)
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default stderr logging."""


class MockLabelPrinter:
    """A lightweight HTTP server that acts as a mock label printer.

    Captures all POST requests so tests can inspect what Homebox sent.
    """

    def __init__(self, port: int) -> None:
        self.port = port
        self.requests: list[PrintRequest] = []
        self._server = http.server.HTTPServer(("", port), _PrinterHandler)
        self._server.captured_requests = self.requests  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=5)

    def clear(self) -> None:
        self.requests.clear()


@pytest.fixture(scope="session")
def mock_label_printer() -> Generator[MockLabelPrinter, None, None]:
    """Start a mock HTTP printer server for the test session.

    Homebox's print command will POST label PNGs to this server.
    Tests can inspect ``mock_label_printer.requests`` to verify
    what was received.
    """
    port = _find_free_port()
    printer = MockLabelPrinter(port)
    printer.start()
    yield printer
    printer.stop()


# ---------------------------------------------------------------------------
# Docker Homebox Container Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def homebox_container(
    mock_label_printer: MockLabelPrinter,
) -> Generator[tuple[str, str], None, None]:
    """Start a disposable Homebox Docker container for the test session.

    The container runs ``ghcr.io/sysadminsmedia/homebox:latest`` with
    ``HBOX_DEMO=true`` which auto-populates sample data and creates the
    ``demo@example.com`` / ``demo`` user.  The label maker print command
    is configured to POST the label PNG to the ``mock_label_printer``
    HTTP server running on the host.

    Yields ``(base_url, container_name)`` tuple.
    """
    container_name = f"homebox-test-{uuid.uuid4().hex[:8]}"
    host_port = _find_free_port()
    base_url = f"http://localhost:{host_port}"

    # The print command POSTs the label file to the mock printer on the host.
    # host.docker.internal resolves to the host on Docker Desktop (Win/Mac).
    printer_url = f"http://host.docker.internal:{mock_label_printer.port}/print"
    print_cmd = f"wget -q -O /dev/null --post-file {{{{.FileName}}}} {printer_url}"

    # Start the container — skip the entire session if Docker is unavailable.
    # Timeout covers image pull which can be slow on first run.
    try:
        result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", container_name,
                "--add-host=host.docker.internal:host-gateway",
                "-p", f"{host_port}:{HOMEBOX_CONTAINER_PORT}",
                "-e", "HBOX_DEMO=true",
                "-e", "HBOX_MODE=production",
                "-e", f"HBOX_LABEL_MAKER_PRINT_COMMAND={print_cmd}",
                HOMEBOX_IMAGE,
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 5 min: covers image pull on first run
        )
    except subprocess.TimeoutExpired:
        pytest.skip("Docker container start timed out (image pull may be slow)")
    if result.returncode != 0:
        pytest.skip(f"Docker container failed to start (is Docker running?): {result.stderr}")

    try:
        _wait_for_homebox(base_url)
        yield base_url, container_name
    finally:
        # Teardown: force-remove the container (handles both running and stopped)
        subprocess.run(
            ["docker", "rm", "--force", container_name],
            capture_output=True,
            text=True,
        )


class TestSettings(BaseSettings):
    """Test configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="HBC_",
        extra="ignore",
        env_file=".env",  # Load from .env file
        env_file_encoding="utf-8",
    )

    # Legacy OpenAI config (kept for backwards compatibility in tests)
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    # New generic LLM config (preferred)
    llm_api_key: str = ""
    llm_model: str = ""
    llm_api_base: str | None = None
    llm_allow_unsafe_models: bool = False


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    """Provide test settings instance."""
    return TestSettings()


@pytest.fixture(scope="session")
def api_key(test_settings: TestSettings) -> str:
    """Provide LLM API key, skipping test if not set."""
    key = (test_settings.llm_api_key or test_settings.openai_api_key or "").strip()
    if not key:
        pytest.skip("HBC_LLM_API_KEY (or legacy HBC_OPENAI_API_KEY) must be set for AI tests.")
    return key


@pytest.fixture(scope="session")
def model(test_settings: TestSettings) -> str:
    """Provide LLM model name."""
    return (test_settings.llm_model or test_settings.openai_model or "gpt-5-mini").strip()


@pytest.fixture(scope="session")
def openai_api_key() -> str:
    """Provide OpenAI API key, skipping test if not set."""
    key = os.environ.get("TEST_OPENAI_API_KEY", "").strip()
    if not key:
        pytest.skip("TEST_OPENAI_API_KEY must be set for OpenAI tests.")
    return key


@pytest.fixture(scope="session")
def openai_model() -> str:
    """Provide OpenAI model name."""
    return os.environ.get("TEST_OPENAI_MODEL", "gpt-5-mini").strip()


@pytest.fixture(scope="session")
def claude_api_key() -> str:
    """Provide Claude API key, skipping test if not set."""
    key = os.environ.get("TEST_CLAUDE_API_KEY", "").strip()
    if not key:
        pytest.skip("TEST_CLAUDE_API_KEY must be set for Claude tests.")
    return key


@pytest.fixture(scope="session")
def claude_model() -> str:
    """Provide Claude model name."""
    return os.environ.get("TEST_CLAUDE_MODEL", "claude-sonnet-4-5").strip()


@pytest.fixture(scope="session")
def homebox_api_url(homebox_container: tuple[str, str]) -> str:
    """Provide Homebox API URL derived from the Docker container."""
    base_url, _name = homebox_container
    return f"{base_url}/api/v1"


@pytest.fixture(scope="session")
def homebox_container_name(homebox_container: tuple[str, str]) -> str:
    """Provide the Docker container name for docker exec commands."""
    _url, container_name = homebox_container
    return container_name


@pytest.fixture(scope="session")
def homebox_credentials() -> tuple[str, str]:
    """Provide Homebox demo credentials (created by HBOX_DEMO=true)."""
    return DEMO_USERNAME, DEMO_PASSWORD


# ---------------------------------------------------------------------------
# Settings Override Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function", autouse=True)
def reset_settings() -> Generator[None, None, None]:
    """Reset settings to clean state before each test (autouse).

    This ensures test isolation by clearing the settings cache before and
    after each test. All modules access settings via config.settings.
    """
    from homebox_companion.core import config
    from homebox_companion.core.config import get_settings

    get_settings.cache_clear()
    config.settings = get_settings()

    yield

    get_settings.cache_clear()
    config.settings = get_settings()


@pytest.fixture(scope="module")
def allow_unsafe_models() -> Generator[None, None, None]:
    """Enable HBC_LLM_ALLOW_UNSAFE_MODELS for the test module.

    This fixture reloads the app settings after modifying the environment
    variable. All modules access settings via config.settings, so updating
    the config module is sufficient.
    """
    from homebox_companion.core import config
    from homebox_companion.core.config import get_settings

    # Store original value
    original = os.environ.get("HBC_LLM_ALLOW_UNSAFE_MODELS")

    # Set new value and reload settings
    os.environ["HBC_LLM_ALLOW_UNSAFE_MODELS"] = "true"
    get_settings.cache_clear()
    config.settings = get_settings()

    yield

    # Restore original state
    if original is None:
        os.environ.pop("HBC_LLM_ALLOW_UNSAFE_MODELS", None)
    else:
        os.environ["HBC_LLM_ALLOW_UNSAFE_MODELS"] = original
    get_settings.cache_clear()
    config.settings = get_settings()


# ---------------------------------------------------------------------------
# Image Path Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def single_item_single_image_path() -> Path:
    """Path to single item single image test asset."""
    path = ASSETS_DIR / "single_item_single_image.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


@pytest.fixture(scope="session")
def single_item_multi_image_1_path() -> Path:
    """Path to first multi-image test asset (single item)."""
    path = ASSETS_DIR / "single_item_multi_image_1.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


@pytest.fixture(scope="session")
def single_item_multi_image_2_path() -> Path:
    """Path to second multi-image test asset (single item)."""
    path = ASSETS_DIR / "single_item_multi_image_2.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


@pytest.fixture(scope="session")
def multi_item_single_image_path() -> Path:
    """Path to multi-item single image test asset."""
    path = ASSETS_DIR / "multi_item_single_image.jpg"
    if not path.exists():
        pytest.skip(f"Test asset not found: {path}")
    return path


# ---------------------------------------------------------------------------
# Resource Cleanup Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cleanup_items(homebox_api_url: str, homebox_credentials: tuple[str, str]):
    """Track and cleanup items created during tests.

    Usage in tests:
        async def test_something(cleanup_items):
            item_id = await create_item(...)
            cleanup_items.append(item_id)  # Will be deleted after test
    """
    from homebox_companion import HomeboxClient

    created_ids: list[str] = []
    yield created_ids

    # Teardown: delete all created items (best effort)
    if created_ids:
        username, password = homebox_credentials
        try:
            async with HomeboxClient(base_url=homebox_api_url) as client:
                response = await client.login(username, password)
                token = response["token"]
                for item_id in created_ids:
                    try:
                        await client.delete_item(token, item_id)
                    except Exception:
                        # Best effort cleanup - don't fail test if cleanup fails
                        pass
        except Exception:
            # If we can't login or cleanup, just continue
            pass


@pytest_asyncio.fixture
async def cleanup_locations(homebox_api_url: str, homebox_credentials: tuple[str, str]):
    """Track and cleanup locations created during tests.

    Usage in tests:
        async def test_something(cleanup_locations):
            location_id = await create_location(...)
            cleanup_locations.append(location_id)  # Will be deleted after test
    """
    from homebox_companion import HomeboxClient

    created_ids: list[str] = []
    yield created_ids

    # Teardown: delete all created locations (best effort)
    if created_ids:
        username, password = homebox_credentials
        try:
            async with HomeboxClient(base_url=homebox_api_url) as client:
                response = await client.login(username, password)
                token = response["token"]
                for location_id in created_ids:
                    try:
                        # Homebox API typically uses DELETE /locations/{id}
                        await client.client.delete(
                            f"{client.base_url}/locations/{location_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                    except Exception:
                        # Best effort cleanup
                        pass
        except Exception:
            pass
