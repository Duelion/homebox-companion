"""Production-image storage regression; no paid provider calls.

Build once with docker build -t homebox-companion:storage-test . before running.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from collections.abc import Generator
from pathlib import Path

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


def test_fresh_volume_settings_survive_restart_and_replacement(
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
    run_args = (
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
    docker("run", "-d", "--name", name, *run_args)
    expected = [{"name": "Storage material", "ai_instruction": "Preserve Unicode: acero — 鋼"}]
    expected_preferences = {
        "default_tag_id": "storage-tag-id",
        "output_language": "Spanish",
        "name": "Storage naming instruction — retained",
    }
    try:
        assert docker("exec", name, "id", "-u") != "0"
        original_container = docker("inspect", "--format", "{{.Id}}", name)
        for phase in ("initial", "restart", "replacement"):
            if phase == "restart":
                docker("restart", name)
            if phase == "replacement":
                docker("rm", "--force", name)
                name = f"companion-replacement-{uuid.uuid4().hex}"
                docker("run", "-d", "--name", name, *run_args)
                assert docker("inspect", "--format", "{{.Id}}", name) != original_container
                assert docker("exec", name, "id", "-u") != "0"
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
                preferences = client.get("/api/settings/field-preferences", headers=headers)
                assert preferences.status_code == 200
                if phase != "initial":
                    assert fields.json() == expected
                    assert profiles.json()["profiles"][0]["name"] == "Storage profile"
                    for key, value in expected_preferences.items():
                        assert preferences.json()[key] == value
                    effective = json.loads(
                        docker(
                            "exec",
                            name,
                            "uv",
                            "run",
                            "--no-sync",
                            "python",
                            "-c",
                            "import json; from homebox_companion.core.field_preferences import load_field_preferences; "
                            "print(json.dumps(load_field_preferences().model_dump()))",
                        )
                    )
                    for key, value in expected_preferences.items():
                        assert effective[key] == value
                else:
                    assert fields.json() == []
                    saved = client.put("/api/settings/custom-fields", headers=headers, json=expected)
                    assert saved.status_code == 200
                    assert saved.json() == expected
                    saved_preferences = client.put(
                        "/api/settings/field-preferences", headers=headers, json=expected_preferences
                    )
                    assert saved_preferences.status_code == 200
                    profile_name = profiles.json()["profiles"][0]["name"]
                    saved_profile = client.put(
                        f"/api/llm/profiles/{profile_name}",
                        headers=headers,
                        json={"new_name": "Storage profile"},
                    )
                    assert saved_profile.status_code == 200
        assert "PermissionError" not in docker("logs", name)
        assert docker("exec", name, "find", "/app/data", "-name", ".settings-storage-*") == ""
    finally:
        docker("rm", "--force", name)


@pytest.mark.parametrize("layout", ["fresh-data", "existing-data", "bind-data", "explicit-config"])
def test_json_layout_survives_save_reset_and_replacement(
    companion_image: str, storage_volume: str, tmp_path: Path, layout: str
) -> None:
    """Exercise real Linux links and mounts without starting an HTTP server."""
    config_volume = f"companion-config-{uuid.uuid4().hex}"
    mounts = ["-v", f"{storage_volume}:/app/data"]
    bind_owner = (tmp_path.stat().st_uid, tmp_path.stat().st_gid)
    if layout == "bind-data":
        mounts = ["-v", f"{tmp_path.resolve()}:/app/data"]
    if layout == "explicit-config":
        docker("volume", "create", config_volume)
        mounts.extend(["-v", f"{config_volume}:/app/config"])
    try:
        if layout == "bind-data":
            # This disposable host directory must be writable by the image user
            # on Linux too; restore its host ownership during cleanup.
            docker(
                "run",
                "--rm",
                "--user",
                "0",
                *mounts,
                companion_image,
                "python",
                "-c",
                "import os; os.chown('/app/data',1000,1000)",
            )
        if layout == "existing-data":
            # Populate an older data volume before Docker can copy image contents.
            previous_settings = (
                "version: 2\nfield_preferences: {name: inactive, default_tag_id: null}\n"
                "llm_profiles:\n- name: Existing profile\n  model: gpt-5.6-luna\n"
                "  status: primary\n  api_key: storage-sentinel-no-provider-call\n"
                "custom_fields:\n- name: Existing material\n  ai_instruction: Preserve steel\n"
            )
            docker(
                "run",
                "--rm",
                "--user",
                "0",
                "-v",
                f"{storage_volume}:/seed",
                companion_image,
                "python",
                "-c",
                "import os; from pathlib import Path; os.chown('/seed',1000,1000); "
                f"Path('/seed/settings.yaml').write_text({previous_settings!r})",
            )
        if layout == "explicit-config":
            docker(
                "run",
                "--rm",
                "--user",
                "0",
                "-v",
                f"{config_volume}:/seed",
                companion_image,
                "python",
                "-c",
                "import os; from pathlib import Path; os.chown('/seed',1000,1000); "
                "p=Path('/seed/field_preferences.json'); p.write_text('{\"name\":\"mounted JSON\"}'); "
                "os.chown(p,1000,1000)",
            )
        exercise = """
from pathlib import Path
from homebox_companion.core.field_preferences import (
    PREFERENCES_FILE as p, get_defaults, load_field_preferences,
    reset_field_preferences, save_field_preferences,
)
from homebox_companion.core.persistent_settings import check_settings_storage, get_settings
check_settings_storage()
check_settings_storage(p.resolve().parent)
settings = Path('/app/data/settings.yaml')
if settings.exists():
    loaded = get_settings()
    assert loaded.llm_profiles[0].name == 'Existing profile'
    assert loaded.custom_fields[0].name == 'Existing material'
    assert loaded.field_preferences == {'name': 'inactive', 'default_tag_id': None}
    assert load_field_preferences().name == get_defaults().name
original = settings.read_bytes() if settings.exists() else None
linked = p.is_symlink()
if not linked:
    assert load_field_preferences().name == 'mounted JSON'
    # A separate data-file sentinel must never override an explicit config mount.
    Path('/app/data/config').mkdir(exist_ok=True)
    Path('/app/data/config/field_preferences.json').write_text('{"name":"data sentinel"}')
save_field_preferences(get_defaults().model_copy(update={'name': 'saved JSON — 鋼'}))
assert load_field_preferences().name == 'saved JSON — 鋼'
assert p.is_symlink() == linked
reset_field_preferences()
assert load_field_preferences().name == get_defaults().name
assert not p.exists()
assert p.is_symlink() == linked
save_field_preferences(get_defaults().model_copy(update={'name': 'replacement JSON'}))
assert p.is_symlink() == linked
assert (settings.read_bytes() if settings.exists() else None) == original
if not linked:
    assert Path('/app/data/config/field_preferences.json').read_text() == '{"name":"data sentinel"}'
"""
        docker("run", "--rm", *mounts, companion_image, "uv", "run", "--no-sync", "python", "-c", exercise)
        restored = docker(
            "run",
            "--rm",
            *mounts,
            companion_image,
            "uv",
            "run",
            "--no-sync",
            "python",
            "-c",
            "from homebox_companion.core.field_preferences import load_field_preferences; "
            "print(load_field_preferences().name)",
        )
        assert restored == "replacement JSON"
    finally:
        if layout == "bind-data":
            docker(
                "run",
                "--rm",
                "--user",
                "0",
                *mounts,
                companion_image,
                "python",
                "-c",
                "import os; from pathlib import Path; root=Path('/app/data'); "
                f"[os.chown(p,{bind_owner[0]},{bind_owner[1]}) for p in [root,*root.rglob('*')]]",
            )
        if layout == "explicit-config":
            docker("volume", "rm", config_volume)


@pytest.mark.parametrize("directory", ["/app/data", "/app/config"])
def test_unwritable_storage_fails_before_healthy_startup(
    companion_image: str, storage_volume: str, directory: str
) -> None:
    name = f"companion-unwritable-{uuid.uuid4().hex}"
    # Seed an existing mount before image contents can populate it. Config mounts
    # from older deployments contain a regular JSON file rather than a link.
    filename = "settings.yaml" if directory == "/app/data" else "field_preferences.json"
    sentinel = "retained sentinel" if directory == "/app/data" else '{"name":"retained sentinel"}'
    docker(
        "run",
        "--rm",
        "--user",
        "0",
        "-v",
        f"{storage_volume}:/seed",
        companion_image,
        "python",
        "-c",
        "import os; from pathlib import Path; os.chown('/seed',1000,1000); "
        f"p=Path('/seed/{filename}'); p.write_text({sentinel!r}); os.chown(p,1000,1000)",
    )
    docker(
        "run",
        "-d",
        "--name",
        name,
        "-v",
        f"{storage_volume}:{directory}:ro",
        "-e",
        "HBC_LLM_API_KEY=storage-sentinel-no-provider-call",
        companion_image,
    )
    try:
        assert docker("wait", name) != "0"
        diagnostic = docker("logs", name)
        assert f"Settings storage is not writable at '{directory}'" in diagnostic
        assert "UID " in diagnostic and "GID " in diagnostic
        assert "ownership" in diagnostic
        assert docker("inspect", "--format", "{{.State.Status}}", name) == "exited"
        retained = docker(
            "run",
            "--rm",
            "-v",
            f"{storage_volume}:{directory}:ro",
            companion_image,
            "cat",
            f"{directory}/{filename}",
        )
        assert retained == sentinel
    finally:
        docker("rm", "--force", name)
