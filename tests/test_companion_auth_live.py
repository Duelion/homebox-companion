"""Companion's real Homebox boundary under both supported authentication modes."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from conftest import HomeboxAuth, HomeboxTestAccount, _find_free_port
from pydantic import SecretStr

from homebox_companion import HomeboxAuthError, HomeboxClient
from homebox_companion.core.config import Settings
from server.app import create_app

pytestmark = pytest.mark.live


@pytest.fixture
def homebox_api_url(homebox_test_account: HomeboxTestAccount) -> str:
    return homebox_test_account.api_url


@pytest.fixture
def homebox_credentials(homebox_test_account: HomeboxTestAccount) -> tuple[str, str]:
    return homebox_test_account.email, homebox_test_account.password


@pytest_asyncio.fixture
async def companion_client(
    homebox_test_account: HomeboxTestAccount,
    homebox_auth: HomeboxAuth,
) -> AsyncGenerator[tuple[httpx.AsyncClient, dict[str, str]]]:
    """Start the app with an explicit setting object and the selected real credential."""
    api_key = SecretStr(homebox_auth.token) if homebox_auth.mode == "api_key" else None
    app = create_app(
        Settings(
            homebox_url=homebox_test_account.server.base_url,
            homebox_api_key=api_key,
            disable_update_check=True,
            llm_api_key="test-only-no-live-llm-call",
        )
    )
    headers = {"X-Companion-Request": "1"} if api_key is not None else {"Authorization": f"Bearer {homebox_auth.token}"}
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://companion.test") as client:
            yield client, headers


@pytest.mark.asyncio
async def test_connection_and_inventory_routes_share_the_selected_auth_context(
    companion_client: tuple[httpx.AsyncClient, dict[str, str]],
    homebox_auth: HomeboxAuth,
    homebox_client: HomeboxClient,
    cleanup_items: list[str],
    cleanup_locations: list[str],
    single_item_single_image_path,
) -> None:
    """Key mode has no browser bearer; legacy mode carries the session bearer."""
    client, headers = companion_client
    config = await client.get("/api/config")
    assert config.status_code == 200
    assert config.json()["auth_mode"] == ("api_key" if homebox_auth.mode == "api_key" else "legacy")

    connection = await client.get("/api/homebox/connection", headers=headers)
    assert connection.status_code == 200
    body = connection.json()
    assert body["connected"] is True
    assert body["context_id"] and body["user_id"] and body["default_group_id"]

    location = await client.post("/api/locations", headers=headers, json={"name": "Companion live location"})
    assert location.status_code == 200
    location_id = location.json()["id"]
    cleanup_locations.append(location_id)
    locations = await client.get("/api/locations", headers=headers)
    assert locations.status_code == 200
    assert any(row["id"] == location_id for row in locations.json())

    created = await client.post(
        "/api/items",
        headers=headers,
        json={"items": [{"name": "Companion live item", "location_id": location_id, "manufacturer": "Pytest"}]},
    )
    assert created.status_code == 200
    item_id = created.json()["created"][0]["id"]
    cleanup_items.append(item_id)

    uploaded = await client.post(
        f"/api/items/{item_id}/attachments",
        headers=headers,
        files={"file": ("live.jpg", single_item_single_image_path.read_bytes(), "image/jpeg")},
    )
    assert uploaded.status_code == 200
    upstream = await homebox_client.get_item(homebox_auth.token, item_id)
    attachment_id = upstream["attachments"][0]["id"]
    proxied = await client.get(f"/api/items/{item_id}/attachments/{attachment_id}", headers=headers)
    assert proxied.status_code == 200
    assert proxied.content


@pytest.mark.asyncio
async def test_zero_purchase_price_round_trips_through_companion_and_upstream(
    companion_client: tuple[httpx.AsyncClient, dict[str, str]],
    homebox_auth: HomeboxAuth,
    homebox_client: HomeboxClient,
    cleanup_items: list[str],
    cleanup_locations: list[str],
) -> None:
    """A zero price is an explicit extended field, not an omitted value."""
    client, headers = companion_client
    location = await homebox_client.create_location(homebox_auth.token, "Zero-price location")
    cleanup_locations.append(location["id"])

    created = await client.post(
        "/api/items",
        headers=headers,
        json={
            "items": [
                {"name": "Zero-price item", "location_id": location["id"], "purchase_price": 0},
            ]
        },
    )

    assert created.status_code == 200
    item_id = created.json()["created"][0]["id"]
    cleanup_items.append(item_id)
    fresh = await homebox_client.get_item(homebox_auth.token, item_id)
    assert fresh["purchasePrice"] == 0


@pytest.mark.asyncio
async def test_post_create_auth_failure_keeps_real_item_visible_in_response(
    companion_client: tuple[httpx.AsyncClient, dict[str, str]],
    homebox_auth: HomeboxAuth,
    homebox_client: HomeboxClient,
    cleanup_items: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject an auth failure after the real Homebox POST, in both auth modes."""
    client, headers = companion_client
    original_update = HomeboxClient.update_item

    async def reject_extended_update(self, token, item_id, item_data):
        if item_data.get("name") == "Incomplete creation regression":
            # Register the real ID for cleanup even if the response assertion fails.
            cleanup_items.append(item_id)
            raise HomeboxAuthError("Simulated expiry after creation")
        return await original_update(self, token, item_id, item_data)

    monkeypatch.setattr(HomeboxClient, "update_item", reject_extended_update)
    response = await client.post(
        "/api/items",
        headers=headers,
        json={"items": [{"name": "Incomplete creation regression", "manufacturer": "Not saved"}]},
    )

    assert response.status_code == 207
    assert len(response.json()["created"]) == 1
    item_id = response.json()["created"][0]["id"]
    assert item_id in cleanup_items
    assert response.json()["errors"]
    fresh = await homebox_client.get_item(homebox_auth.token, item_id)
    assert fresh["name"] == "Incomplete creation regression"
    assert fresh.get("manufacturer") != "Not saved"


@pytest.mark.asyncio
async def test_key_mode_rejects_invalid_configured_credentials_without_browser_auth(
    homebox_test_account: HomeboxTestAccount,
) -> None:
    app = create_app(
        Settings(
            homebox_url=homebox_test_account.server.base_url,
            homebox_api_key=SecretStr("hb_invalid_configured_test_key"),
            disable_update_check=True,
        )
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://companion.test"
        ) as client:
            rejected = await client.get("/api/homebox/connection")
    assert rejected.status_code == 502
    assert rejected.json()["code"] == "HOMEBOX_API_KEY_REJECTED"


@pytest.mark.parametrize("mode", [pytest.param("credentials", id="credentials"), pytest.param("api_key", id="api_key")])
def test_fresh_process_selects_configured_auth_before_imports(
    mode: str,
    homebox_test_account: HomeboxTestAccount,
    homebox_key_factory,
    tmp_path,
) -> None:
    """A child uvicorn process proves env selection occurs before application imports."""
    port = _find_free_port()
    (tmp_path / ".env").write_text("HBC_HOMEBOX_API_KEY=hb_contrasting_dotenv_key\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        {
            "HBC_HOMEBOX_URL": homebox_test_account.server.base_url,
            "HBC_HOMEBOX_API_KEY": "" if mode == "credentials" else homebox_key_factory().token,
            "HBC_LLM_API_KEY": "test-only-no-live-llm-call",
            "HBC_DISABLE_UPDATE_CHECK": "true",
            "HBC_SERVER_PORT": str(port),
        }
    )
    log_path = tmp_path / "companion-child.log"
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=tmp_path,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(
                        f"Fresh Companion process exited:\n{log_path.read_text(encoding='utf-8')[-4000:]}",
                        pytrace=False,
                    )
                try:
                    with httpx.Client(timeout=2, trust_env=False) as client:
                        response = client.get(f"{base_url}/api/config")
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
            else:
                diagnostics = log_path.read_text(encoding="utf-8")[-4000:]
                pytest.fail(
                    f"Fresh Companion process did not expose /api/config:\n{diagnostics}",
                    pytrace=False,
                )
            assert response.json()["auth_mode"] == ("legacy" if mode == "credentials" else "api_key")
            if mode == "credentials":
                with httpx.Client(timeout=10, trust_env=False) as client:
                    login = client.post(
                        f"{base_url}/api/login",
                        json={"username": homebox_test_account.email, "password": homebox_test_account.password},
                    )
                assert login.status_code == 200
                headers = {"Authorization": f"Bearer {login.json()['token']}"}
            else:
                headers = {}
            with httpx.Client(timeout=10, trust_env=False) as client:
                connection = client.get(f"{base_url}/api/homebox/connection", headers=headers)
                locations = client.get(f"{base_url}/api/locations", headers=headers)
            assert connection.status_code == 200
            assert locations.status_code == 200
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
