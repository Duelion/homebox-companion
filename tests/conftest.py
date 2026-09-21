"""Minimal pytest configuration for Homebox Companion tests."""

from __future__ import annotations

import asyncio
import http.server
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import httpx
import pytest
import pytest_asyncio
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from homebox_companion import HomeboxClient


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

HOMEBOX_IMAGE = "ghcr.io/sysadminsmedia/homebox@sha256:b1ad7e3c63f732a5f6daa466e8116be4f545b3b120383a64dcb62beb00a660cc"
HOMEBOX_CONTAINER_PORT = 7745

# Demo user credentials (created automatically by HBOX_DEMO=true)
DEMO_USERNAME = "demo@example.com"
DEMO_PASSWORD = "demodemo"

# Test assets directory
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_homebox(base_url: str, timeout: float = 60.0, interval: float = 1.0) -> None:
    """Wait for HTTP, demo login and seeded locations/tags, not just process readiness."""
    deadline = time.monotonic() + timeout
    stage = "HTTP readiness"
    token: str | None = None
    api_url = f"{base_url}/api/v1"
    with httpx.Client(timeout=3.0, trust_env=False) as setup:
        while time.monotonic() < deadline:
            delay = interval
            try:
                if setup.get(f"{api_url}/status").status_code == 200:
                    if token is None:
                        stage = "demo login"
                        response = setup.post(
                            f"{api_url}/users/login",
                            data={"username": DEMO_USERNAME, "password": DEMO_PASSWORD, "stayLoggedIn": "true"},
                        )
                        if response.status_code == 200:
                            token = _response_token(response)
                            setup.cookies.clear()
                        elif response.status_code == 429:
                            delay = max(interval, float(response.headers.get("Retry-After", "2")))
                        elif response.status_code != 401:
                            _expect_status(response, 200, "Demo bootstrap login")
                    if token is not None:
                        stage = "demo locations and tags"
                        headers = {"Authorization": f"Bearer {token}"}
                        locations = setup.get(f"{api_url}/entities", headers=headers, params={"isLocation": "true"})
                        tags = setup.get(f"{api_url}/tags", headers=headers)
                        _expect_status(locations, 200, "Demo location readiness")
                        _expect_status(tags, 200, "Demo tag readiness")
                        if locations.json().get("items") and isinstance(tags.json(), list):
                            _expect_status(setup.post(f"{api_url}/users/logout", headers=headers), 204, "Setup logout")
                            # Homebox applies a short per-address login throttle.  The next test client
                            # must be able to prove the supported login flow rather than inherit setup pressure.
                            time.sleep(5)
                            return
            except httpx.HTTPError:
                pass  # The process may still be starting; preserve the bounded deadline.
            time.sleep(min(delay, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"Homebox was not ready within {timeout}s (waiting for {stage})")


def _expect_status(response: httpx.Response, expected: int, action: str) -> None:
    """Report setup failures without dumping auth response bodies or request headers."""
    if response.status_code != expected:
        pytest.fail(f"{action}: expected HTTP {expected}, got {response.status_code}", pytrace=False)


def _response_token(response: httpx.Response) -> str:
    """Extract either credential without including its contents in diagnostics."""
    token = response.json().get("token")
    if not isinstance(token, str) or not token.strip():
        pytest.fail("Homebox did not return a usable token", pytrace=False)
    return token.removeprefix("Bearer ")


def _require_docker() -> None:
    """Skip only an optional local Docker run; CI setup failures are failures."""
    available = shutil.which("docker") is not None
    if available:
        try:
            available = (
                subprocess.run(
                    ["docker", "info"],
                    capture_output=True,
                    timeout=15,
                    check=False,
                ).returncode
                == 0
            )
        except subprocess.TimeoutExpired:
            available = False
    if not available:
        if os.environ.get("CI"):
            pytest.fail("Docker is required for Homebox live tests in CI", pytrace=False)
        pytest.skip("Docker is not available for Homebox live tests")


@dataclass
class HomeboxDockerServer:
    """Disposable Homebox lifecycle with a rediscoverable loopback port."""

    name: str
    environment: dict[str, str]
    volume: str | None = None
    docker_args: tuple[str, ...] = ()
    base_url: str = field(init=False, repr=False)

    def start(self) -> None:
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            self.name,
            *self.docker_args,
            "-p",
            f"127.0.0.1::{HOMEBOX_CONTAINER_PORT}",
        ]
        if self.volume is not None:
            command.extend(["-v", f"{self.volume}:/data"])
        for key, value in self.environment.items():
            command.extend(["-e", f"{key}={value}"])
        command.append(HOMEBOX_IMAGE)
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            pytest.fail(f"Docker container failed to start: {result.stderr}", pytrace=False)
        self.rediscover_port()
        inspect = subprocess.run(
            ["docker", "inspect", "--format", "{{.Config.Image}} [{{.Image}}]", self.name],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        logger.info("Verified Homebox container started using image: {}", inspect.stdout.strip() or "unknown")

    def rediscover_port(self) -> None:
        result = subprocess.run(
            ["docker", "port", self.name, f"{HOMEBOX_CONTAINER_PORT}/tcp"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        self.base_url = f"http://{result.stdout.strip().splitlines()[0]}"

    def restart(self) -> None:
        """Recreate the container with retained data and rediscover Docker's new port."""
        subprocess.run(["docker", "rm", "--force", self.name], capture_output=True, text=True, timeout=30)
        self.start()
        _wait_for_status(self)

    def remove(self) -> None:
        subprocess.run(["docker", "rm", "--force", "--volumes", self.name], capture_output=True, text=True, timeout=30)
        if self.volume is not None:
            subprocess.run(
                ["docker", "volume", "rm", "--force", self.volume], capture_output=True, text=True, timeout=30
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
        self.server.captured_requests.append(  # ty: ignore
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
        self._server.captured_requests = self.requests  # ty: ignore
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=5)
        self._server.server_close()

    def clear(self) -> None:
        self.requests.clear()


@pytest.fixture(scope="session")
def mock_label_printer() -> Generator[MockLabelPrinter]:
    """Start a mock HTTP printer server for the test session.

    Homebox's print command will POST label PNGs to this server.
    Tests can inspect ``mock_label_printer.requests`` to verify
    what was received.
    """
    port = _find_free_port()
    printer = MockLabelPrinter(port)
    printer.start()
    try:
        yield printer
    finally:
        printer.stop()


# ---------------------------------------------------------------------------
# Docker Homebox Container Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def homebox_container(
    mock_label_printer: MockLabelPrinter,
) -> Generator[tuple[str, str]]:
    """Start a disposable Homebox Docker container for the test session.

    The container runs ``ghcr.io/sysadminsmedia/homebox:0.26.2`` with
    ``HBOX_DEMO=true`` which auto-populates sample data and creates the
    ``demo@example.com`` / ``demodemo`` user.  The label maker print command
    is configured to POST the label PNG to the ``mock_label_printer``
    HTTP server running on the host.

    Yields ``(base_url, container_name)`` tuple.
    """
    container_name = f"homebox-test-{uuid.uuid4().hex[:8]}"

    # The print command POSTs the label file to the mock printer on the host.
    # host.docker.internal resolves to the host on Docker Desktop (Win/Mac).
    printer_url = f"http://host.docker.internal:{mock_label_printer.port}/print"
    print_cmd = f"wget -q -O /dev/null --post-file {{{{.FileName}}}} {printer_url}"

    _require_docker()
    try:
        server = HomeboxDockerServer(
            name=container_name,
            environment={
                "HBOX_DEMO": "true",
                "HBOX_DEMO_PASSWORD": DEMO_PASSWORD,
                "HBOX_MODE": "production",
                "HBOX_OPTIONS_ALLOW_ANALYTICS": "false",
                "HBOX_AUTH_API_KEY_PEPPER": "homebox-companion-test-pepper-value-at-least-32-bytes",
                "HBOX_LABEL_MAKER_PRINT_COMMAND": print_cmd,
            },
            docker_args=("--add-host=host.docker.internal:host-gateway",),
        )
        server.start()
        _wait_for_homebox(server.base_url)
        yield server.base_url, container_name
    finally:
        server.remove() if "server" in locals() else subprocess.run(
            ["docker", "rm", "--force", "--volumes", container_name],
            capture_output=True,
            text=True,
            timeout=30,
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
    openai_model: str = "gpt-5.6-luna"

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
    return (test_settings.llm_model or test_settings.openai_model or "gpt-5.6-luna").strip()


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
    return os.environ.get("TEST_OPENAI_MODEL", "gpt-5.6-luna").strip()


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
    """Provide seeded Homebox credentials (created by HBOX_DEMO=true)."""
    return DEMO_USERNAME, DEMO_PASSWORD


def _wait_for_status(server: HomeboxDockerServer, timeout: float = 60.0) -> None:
    """Wait for an unseeded Homebox server without authenticating the tested client."""
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=3.0, trust_env=False) as setup:
        while time.monotonic() < deadline:
            try:
                if setup.get(f"{server.base_url}/api/v1/status").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(1)
    raise RuntimeError(f"Homebox was not ready within {timeout}s")


@dataclass(frozen=True)
class HomeboxTestAccount:
    """An isolated registered identity and its setup-only control bearer."""

    server: HomeboxDockerServer = field(repr=False)
    email: str
    password: str = field(repr=False)
    control_token: str = field(repr=False)

    @property
    def api_url(self) -> str:
        return f"{self.server.base_url}/api/v1"


@dataclass(frozen=True)
class HomeboxKey:
    """A one-time Homebox key, redacted from pytest diagnostics."""

    id: str
    token: str = field(repr=False)


@pytest.fixture(scope="session")
def isolated_homebox_server() -> Generator[HomeboxDockerServer]:
    """Run production Homebox with persistent test-only storage for upstream contracts."""
    _require_docker()
    suffix = uuid.uuid4().hex[:10]
    server = HomeboxDockerServer(
        name=f"homebox-isolated-{suffix}",
        volume=f"homebox-isolated-data-{suffix}",
        environment={
            "HBOX_DEMO": "false",
            "HBOX_MODE": "production",
            "HBOX_OPTIONS_ALLOW_REGISTRATION": "true",
            "HBOX_OPTIONS_ALLOW_LOCAL_LOGIN": "true",
            "HBOX_OPTIONS_ALLOW_ANALYTICS": "false",
            "HBOX_AUTH_API_KEY_PEPPER": "homebox-companion-isolated-test-pepper-value-at-least-32-bytes",
        },
    )
    try:
        server.start()
        _wait_for_status(server)
        yield server
    finally:
        server.remove()


def _register_test_account(server: HomeboxDockerServer) -> HomeboxTestAccount:
    """Use raw bootstrap HTTP so application authentication cannot validate itself."""
    unique = uuid.uuid4().hex
    email = f"pytest-{unique}@example.invalid"
    password = f"pytest-{unique}-Password!"
    api_url = f"{server.base_url}/api/v1"
    with httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as setup:
        registered = setup.post(
            f"{api_url}/users/register",
            json={"name": f"Pytest {unique[:8]}", "email": email, "password": password},
        )
        if registered.status_code != 204:
            logs = subprocess.run(
                ["docker", "logs", "--tail", "120", server.name],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            response_shape = "non-JSON"
            try:
                body = registered.json()
                response_shape = f"JSON keys={sorted(body) if isinstance(body, dict) else type(body).__name__}"
            except ValueError:
                pass
            diagnostics = f"{logs.stdout}\n{logs.stderr}"[-6000:]
            # Homebox logs are deliberately limited to server diagnostics; never emit request bodies or env.
            pytest.fail(
                f"Isolated account registration: expected HTTP 204, got {registered.status_code} ({response_shape}). "
                f"Container diagnostics:\n{diagnostics}",
                pytrace=False,
            )
        logged_in = setup.post(
            f"{api_url}/users/login",
            data={"username": email, "password": password, "stayLoggedIn": "true"},
        )
        _expect_status(logged_in, 200, "Isolated account login")
        token = _response_token(logged_in)
        item_type = setup.post(
            f"{api_url}/entity-types",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Pytest Item", "isLocation": False},
        )
        _expect_status(item_type, 201, "Isolated item-type creation")
    return HomeboxTestAccount(server=server, email=email, password=password, control_token=token)


@pytest.fixture
def homebox_test_account(isolated_homebox_server: HomeboxDockerServer) -> Generator[HomeboxTestAccount]:
    """A new account per test, backed by the shared non-demo Docker server."""
    account = _register_test_account(isolated_homebox_server)
    try:
        yield account
    finally:
        with httpx.Client(timeout=15, trust_env=False) as control:
            response = control.post(
                f"{account.api_url}/users/logout",
                headers={"Authorization": f"Bearer {account.control_token}"},
            )
            _expect_status(response, 204, "Isolated account logout")


@pytest.fixture
def homebox_key_factory(homebox_test_account: HomeboxTestAccount):
    """Issue tracked keys and revoke them with independent account control credentials."""
    created: list[HomeboxKey] = []

    def create(*, expires_at: datetime | None = None) -> HomeboxKey:
        with httpx.Client(timeout=15, trust_env=False) as control:
            response = control.post(
                f"{homebox_test_account.api_url}/users/self/api-keys",
                headers={"Authorization": f"Bearer {homebox_test_account.control_token}"},
                json={
                    "name": f"pytest-{uuid.uuid4().hex}",
                    "expiresAt": (expires_at or datetime.now(UTC) + timedelta(hours=2)).isoformat(),
                },
            )
        _expect_status(response, 201, "Tracked API-key creation")
        key = HomeboxKey(id=response.json()["id"], token=_response_token(response))
        if not key.token.startswith("hb_"):
            pytest.fail("Homebox returned an unexpected API-key format", pytrace=False)
        created.append(key)
        return key

    try:
        yield create
    finally:
        with httpx.Client(timeout=15, trust_env=False) as control:
            headers = {"Authorization": f"Bearer {homebox_test_account.control_token}"}
            for key in created:
                response = control.delete(
                    f"{homebox_test_account.api_url}/users/self/api-keys/{key.id}", headers=headers
                )
                if response.status_code != 404:
                    _expect_status(response, 204, "Tracked API-key revocation")


@dataclass(frozen=True)
class HomeboxAuth:
    """An upstream test credential whose secret never appears in fixture reprs."""

    mode: Literal["credentials", "api_key"]
    token: str = field(repr=False)


@pytest.fixture(params=[pytest.param("credentials", id="credentials"), pytest.param("api_key", id="api_key")])
def homebox_auth_mode(request: pytest.FixtureRequest) -> Literal["credentials", "api_key"]:
    """Single auth matrix; a mode-specific test class can override this fixture."""
    return request.param


@pytest.fixture
def homebox_auth(
    homebox_auth_mode: Literal["credentials", "api_key"],
    homebox_api_url: str,
    homebox_credentials: tuple[str, str],
) -> Generator[HomeboxAuth]:
    """Run every consumer with both auth modes; keep setup cookies out of the tested client.

    Legacy lifecycle tests can keep using homebox_credentials directly and run only once.
    A test class can override homebox_auth_mode when its contract is mode-specific.
    """
    mode = homebox_auth_mode
    if mode not in ("credentials", "api_key"):
        pytest.fail("Unsupported Homebox test auth mode", pytrace=False)
    username, password = homebox_credentials
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as control:
        login = control.post(
            f"{homebox_api_url}/users/login",
            data={"username": username, "password": password, "stayLoggedIn": "true"},
        )
        _expect_status(login, 200, "Fixture login")
        session_token = _response_token(login)
        control_headers = {"Authorization": f"Bearer {session_token}"}
        control.cookies.clear()
        key_id: str | None = None
        key_token: str | None = None
        try:
            if mode == "api_key":
                created = control.post(
                    f"{homebox_api_url}/users/self/api-keys",
                    headers=control_headers,
                    json={
                        "name": f"pytest-{uuid.uuid4().hex}",
                        "expiresAt": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
                    },
                )
                _expect_status(created, 201, "Fixture API-key creation")
                key_id = created.json()["id"]
                key_token = _response_token(created)
                if not key_token.startswith("hb_"):
                    pytest.fail("Homebox returned an unexpected API-key format", pytrace=False)
                yield HomeboxAuth(mode=mode, token=key_token)
            else:
                yield HomeboxAuth(mode=mode, token=session_token)
        finally:
            try:
                if key_id is not None:
                    revoked = control.delete(
                        f"{homebox_api_url}/users/self/api-keys/{key_id}",
                        headers=control_headers,
                    )
                    # A lifecycle test may already have revoked its own key.
                    if revoked.status_code != 404:
                        _expect_status(revoked, 204, "Fixture API-key revocation")
                    if key_token is not None:
                        with httpx.Client(timeout=10, trust_env=False) as verifier:
                            rejected = verifier.get(
                                f"{homebox_api_url}/users/self",
                                headers={"Authorization": f"Bearer {key_token}"},
                            )
                            _expect_status(rejected, 401, "Revoked API key must no longer authenticate")
            finally:
                _expect_status(
                    control.post(f"{homebox_api_url}/users/logout", headers=control_headers),
                    204,
                    "Fixture session logout",
                )


@pytest_asyncio.fixture
async def homebox_client(homebox_api_url: str, homebox_auth: HomeboxAuth) -> AsyncGenerator[HomeboxClient]:
    """A fresh client for the selected credential; it must never authenticate through cookies."""
    from homebox_companion import HomeboxClient

    async def require_bearer_without_cookies(request: httpx.Request) -> None:
        if "cookie" in request.headers:
            pytest.fail("Business test client must not send Homebox login cookies", pytrace=False)
        if not request.headers.get("Authorization", "").startswith("Bearer "):
            pytest.fail("Business test client must explicitly send a bearer credential", pytrace=False)

    # The dependency guarantees this client closes before homebox_auth revokes the credential.
    # An injected transport is not owned by HomeboxClient, so close both contexts explicitly.
    async with httpx.AsyncClient(
        timeout=30,
        trust_env=False,
        follow_redirects=False,
        event_hooks={"request": [require_bearer_without_cookies]},
    ) as transport:
        async with HomeboxClient(base_url=homebox_api_url, client=transport) as client:
            if not await client.validate_token(homebox_auth.token):
                pytest.fail(f"Fresh {homebox_auth.mode} credential was rejected", pytrace=False)
            yield client


# ---------------------------------------------------------------------------
# Settings Override Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function", autouse=True)
def reset_settings() -> Generator[None]:
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
def allow_unsafe_models() -> Generator[None]:
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
async def cleanup_items(homebox_client: HomeboxClient, homebox_auth: HomeboxAuth) -> AsyncGenerator[list[str]]:
    """Track and cleanup items created during tests.

    Usage in tests:
        async def test_something(cleanup_items):
            item_id = await create_item(...)
            cleanup_items.append(item_id)  # Will be deleted after test
    """
    created_ids: list[str] = []
    try:
        yield created_ids
    finally:
        await _cleanup_entities(homebox_client, homebox_auth, created_ids)


@pytest_asyncio.fixture
async def cleanup_locations(homebox_client: HomeboxClient, homebox_auth: HomeboxAuth) -> AsyncGenerator[list[str]]:
    """Track and cleanup locations created during tests.

    Usage in tests:
        async def test_something(cleanup_locations):
            location_id = await create_location(...)
            cleanup_locations.append(location_id)  # Will be deleted after test
    """
    created_ids: list[str] = []
    try:
        yield created_ids
    finally:
        await _cleanup_entities(homebox_client, homebox_auth, created_ids)


async def _cleanup_entities(client: HomeboxClient, auth: HomeboxAuth, entity_ids: list[str]) -> None:
    """Delete test entities before auth teardown; allow prior deletion but expose real failures."""
    from homebox_companion.core.exceptions import HomeboxAPIError

    failures: list[str] = []
    for entity_id in reversed(entity_ids):
        try:
            await _wait_for_photo_thumbnail(client, auth, entity_id)
            # Homebox 0.26 uses the same entity endpoint for items and locations.
            await client.delete_item(auth.token, entity_id)
        except HomeboxAPIError as exc:
            if exc.context.get("status_code") != 404:
                failures.append(entity_id)
        except Exception:
            failures.append(entity_id)
    if failures:
        pytest.fail(f"Failed to clean up {len(failures)} Homebox test entities", pytrace=False)


async def _wait_for_photo_thumbnail(client: HomeboxClient, auth: HomeboxAuth, entity_id: str) -> None:
    """Let Homebox finish its asynchronous thumbnail write before deleting a photo entity."""
    from homebox_companion.core.exceptions import HomeboxAPIError

    deadline = time.monotonic() + 15
    while True:
        try:
            entity = await client.get_item(auth.token, entity_id)
            photos = [attachment for attachment in entity.get("attachments", []) if attachment.get("type") == "photo"]
            if not photos or all(photo.get("thumbnail") is not None for photo in photos):
                return
        except HomeboxAPIError as exc:
            # Preserve the cleanup fixture's existing 404 allowance for entities deleted by the test.
            if exc.context.get("status_code") == 404:
                raise
            # SQLite can briefly reject reads while Homebox commits the thumbnail transaction.
            if exc.context.get("status_code") not in {500, 503}:
                raise
        if time.monotonic() >= deadline:
            pytest.fail("Homebox did not finish photo thumbnail generation before cleanup", pytrace=False)
        await asyncio.sleep(0.25)
