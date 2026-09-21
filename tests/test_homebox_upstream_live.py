"""Durable non-demo Homebox API-key contracts using isolated accounts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import HomeboxAuth, HomeboxDockerServer, HomeboxTestAccount, _register_test_account

from homebox_companion import HomeboxClient, ItemCreate

pytestmark = pytest.mark.live


# These local projections let the existing ``homebox_auth`` / ``homebox_client``
# matrix run the business test against a newly registered, non-demo account.
@pytest.fixture
def homebox_api_url(homebox_test_account: HomeboxTestAccount) -> str:
    return homebox_test_account.api_url


@pytest.fixture
def homebox_credentials(homebox_test_account: HomeboxTestAccount) -> tuple[str, str]:
    return homebox_test_account.email, homebox_test_account.password


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_extended_fields_and_attachment_round_trip_for_both_auth_modes(
    homebox_client: HomeboxClient,
    homebox_auth: HomeboxAuth,
    cleanup_items: list[str],
    cleanup_locations: list[str],
    single_item_single_image_path,
) -> None:
    """One business assertion protects both session and API-key transports."""
    token = homebox_auth.token
    location = await homebox_client.create_location(token, name="Isolated upstream location")
    cleanup_locations.append(location["id"])
    item = await homebox_client.create_item(
        token,
        ItemCreate(name="Isolated upstream item", quantity=1, parent_id=location["id"]),  # ty: ignore[unknown-argument]
    )
    cleanup_items.append(item["id"])
    updated = await homebox_client.update_item(
        token,
        item["id"],
        {
            "id": item["id"],
            "name": item["name"],
            "quantity": 1,
            "parentId": location["id"],
            "manufacturer": "Pytest Manufacturing",
            "modelNumber": "MODEL-42",
            "serialNumber": "SERIAL-42",
        },
    )
    assert {key: updated[key] for key in ("manufacturer", "modelNumber", "serialNumber")} == {
        "manufacturer": "Pytest Manufacturing",
        "modelNumber": "MODEL-42",
        "serialNumber": "SERIAL-42",
    }
    await homebox_client.upload_attachment(
        token,
        item["id"],
        single_item_single_image_path.read_bytes(),
        "upstream.jpg",
        "image/jpeg",
        "photo",
    )
    fetched_after_upload = await homebox_client.get_item(token, item["id"])
    attachment_id = fetched_after_upload["attachments"][0]["id"]
    content, content_type = await homebox_client.get_attachment(
        token,
        item["id"],
        attachment_id,
    )
    assert content == single_item_single_image_path.read_bytes()
    assert content_type.startswith("image/jpeg")


def test_missing_and_query_string_credentials_are_rejected(
    homebox_test_account: HomeboxTestAccount,
    homebox_key_factory,
) -> None:
    key = homebox_key_factory()
    with httpx.Client(timeout=15, trust_env=False) as client:
        missing = client.get(f"{homebox_test_account.api_url}/users/self")
        query = client.get(f"{homebox_test_account.api_url}/users/self", params={"token": key.token})
    assert missing.status_code == 401
    assert query.status_code == 401


def test_key_expiry_revocation_and_rotation(
    homebox_test_account: HomeboxTestAccount,
    homebox_key_factory,
) -> None:
    expired = homebox_key_factory(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    first = homebox_key_factory()
    second = homebox_key_factory()
    with httpx.Client(timeout=15, trust_env=False) as client:
        assert (
            client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(expired.token)).status_code == 401
        )
        assert client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(first.token)).status_code == 200
        assert (
            client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(second.token)).status_code == 200
        )
        revoked = client.delete(
            f"{homebox_test_account.api_url}/users/self/api-keys/{first.id}",
            headers=_bearer(homebox_test_account.control_token),
        )
        assert revoked.status_code == 204
        assert client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(first.token)).status_code == 401
        assert (
            client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(second.token)).status_code == 200
        )


def test_key_survives_container_recreation_and_port_rediscovery(
    homebox_test_account: HomeboxTestAccount,
    homebox_key_factory,
    isolated_homebox_server: HomeboxDockerServer,
) -> None:
    key = homebox_key_factory()
    old_url = isolated_homebox_server.base_url
    isolated_homebox_server.restart()
    # Registration data and pepper persist in the named volume, while Docker may change the host port.
    with httpx.Client(timeout=15, trust_env=False) as client:
        assert client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(key.token)).status_code == 200
    assert isolated_homebox_server.base_url.startswith("http://")
    assert old_url != ""


def test_account_group_isolation_and_cookie_precedence(
    homebox_test_account: HomeboxTestAccount,
    homebox_key_factory,
    isolated_homebox_server: HomeboxDockerServer,
) -> None:
    other = _register_test_account(isolated_homebox_server)
    key = homebox_key_factory()
    with httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client:
        owner = client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(key.token)).json()["item"]
        groups = client.get(f"{homebox_test_account.api_url}/groups/all", headers=_bearer(key.token))
        assert groups.status_code == 200 and groups.json()
        other_groups = client.get(f"{other.api_url}/groups/all", headers=_bearer(other.control_token)).json()
        forbidden = client.get(
            f"{homebox_test_account.api_url}/users/self",
            headers={**_bearer(key.token), "X-Tenant": other_groups[0]["id"]},
        )
        assert forbidden.status_code == 403
        login = client.post(
            f"{other.api_url}/users/login",
            data={"username": other.email, "password": other.password, "stayLoggedIn": "true"},
        )
        assert login.status_code == 200
        cookie_identity = client.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(key.token))
        assert cookie_identity.status_code == 200
        assert cookie_identity.json()["item"]["id"] != owner["id"]
    with httpx.Client(timeout=15, trust_env=False) as fresh:
        assert (
            fresh.get(f"{homebox_test_account.api_url}/users/self", headers=_bearer(key.token)).json()["item"]["id"]
            == owner["id"]
        )
