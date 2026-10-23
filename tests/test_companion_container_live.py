"""Production-image storage regression; no paid provider calls.

Build once with docker build -t homebox-companion:storage-test . before running.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from collections.abc import Generator

import httpx
import pytest
from conftest import HomeboxTestAccount, _require_docker

pytestmark = pytest.mark.live


def docker(*args: str, check: bool = True) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=120, check=check)
    return (result.stdout + result.stderr if args[0] == "logs" else result.stdout).strip()


@pytest.fixture(scope="module")
def companion_image() -> str:
    _require_docker()
    image = os.environ.get("TEST_COMPANION_IMAGE", "homebox-companion:storage-test")
    result = subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=15)
    if result.returncode:
        pytest.fail(f"Build the production image first: docker build -t {image} .", pytrace=False)
    return image


@pytest.fixture
def storage_volume(companion_image: str) -> Generator[str]:
    del companion_image
    volume = f"companion-storage-{uuid.uuid4().hex}"
    docker("volume", "create", volume)
    try:
        yield volume
    finally:
        docker("volume", "rm", volume)


def wait_ready(name: str) -> str:
    address = docker("port", name, "8000/tcp").splitlines()[0]
    url = f"http://{address}"
    deadline = time.monotonic() + 60
    with httpx.Client(timeout=2, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                if client.get(f"{url}/api/version").status_code == 200:
                    return url
            except httpx.HTTPError:
                pass
            if docker("inspect", "--format", "{{.State.Running}}", name) == "false":
                break
            time.sleep(0.5)
    pytest.fail(f"Production container did not become ready:\n{docker('logs', name)}", pytrace=False)


def test_fresh_volume_settings_survive_restart(
    companion_image: str, storage_volume: str, homebox_test_account: HomeboxTestAccount
) -> None:
    name = f"companion-storage-{uuid.uuid4().hex}"
    # Both disposable containers use Docker's default bridge. Use the isolated
    # upstream container IP so Linux does not depend on host loopback forwarding.
    upstream_ip = docker(
        "inspect",
        "--format",
        "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
        homebox_test_account.server.name,
    )
    docker(
        "run",
        "-d",
        "--name",
        name,
        "-p",
        "127.0.0.1::8000",
        "-v",
        f"{storage_volume}:/app/data",
        "-e",
        f"HBC_HOMEBOX_URL=http://{upstream_ip}:7745",
        "-e",
        "HBC_LLM_API_KEY=storage-sentinel-no-provider-call",
        "-e",
        "HBC_LLM_MODEL=gpt-5.6-luna",
        "-e",
        "HBC_DISABLE_UPDATE_CHECK=true",
        companion_image,
    )
    expected = [{"name": "Storage material", "ai_instruction": "Preserve Unicode: acero — 鋼"}]
    try:
        assert docker("exec", name, "id", "-u") != "0"
        for restart in (False, True):
            if restart:
                docker("restart", name)
            url = wait_ready(name)
            with httpx.Client(base_url=url, timeout=15, trust_env=False) as client:
                login = client.post(
                    "/api/login",
                    json={
                        "username": homebox_test_account.email,
                        "password": homebox_test_account.password,
                    },
                )
                assert login.status_code == 200
                headers = {"Authorization": f"Bearer {login.json()['token']}"}
                profiles = client.get("/api/llm/profiles", headers=headers)
                assert profiles.status_code == 200
                fields = client.get("/api/settings/custom-fields", headers=headers)
                assert fields.status_code == 200
                if restart:
                    assert fields.json() == expected
                else:
                    assert fields.json() == []
                    saved = client.put("/api/settings/custom-fields", headers=headers, json=expected)
                    assert saved.status_code == 200
                    assert saved.json() == expected
        assert "PermissionError" not in docker("logs", name)
        assert docker("exec", name, "find", "/app/data", "-name", ".settings-storage-*") == ""
    finally:
        docker("rm", "--force", name)


def test_unwritable_storage_fails_before_healthy_startup(companion_image: str, storage_volume: str) -> None:
    name = f"companion-unwritable-{uuid.uuid4().hex}"
    # Seed real persisted data as the image user, then mount read-only to test
    # Linux permission behavior without relying on Windows chmod semantics.
    docker(
        "run",
        "--rm",
        "-v",
        f"{storage_volume}:/app/data",
        companion_image,
        "sh",
        "-c",
        "printf 'retained sentinel' > /app/data/settings.yaml",
    )
    docker(
        "run",
        "-d",
        "--name",
        name,
        "-v",
        f"{storage_volume}:/app/data:ro",
        "-e",
        "HBC_LLM_API_KEY=storage-sentinel-no-provider-call",
        companion_image,
    )
    try:
        assert docker("wait", name) != "0"
        diagnostic = docker("logs", name)
        assert "Settings storage is not writable at '/app/data'" in diagnostic
        assert "UID " in diagnostic and "GID " in diagnostic
        assert "ownership" in diagnostic
        assert docker("inspect", "--format", "{{.State.Status}}", name) == "exited"
        retained = docker(
            "run", "--rm", "-v", f"{storage_volume}:/app/data:ro", companion_image, "cat", "/app/data/settings.yaml"
        )
        assert retained == "retained sentinel"
    finally:
        docker("rm", "--force", name)
