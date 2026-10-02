"""Optional browser -> Companion -> Homebox smoke; see tests/README.md."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from conftest import HomeboxTestAccount, _find_free_port

pytestmark = pytest.mark.live
ROOT = Path(__file__).resolve().parents[1]


def test_reviewed_photo_reaches_homebox(homebox_test_account: HomeboxTestAccount, homebox_key_factory, tmp_path):
    """Drive the real UI, then verify persisted data with an independent control credential."""
    node = shutil.which("node")
    cli = ROOT / "frontend/node_modules/@playwright/test/cli.js"
    build = ROOT / "frontend/build"
    assert node and cli.is_file(), "Install frontend dependencies and Node; see tests/README.md"
    assert (build / "index.html").is_file(), "Build the frontend before running the smoke test"
    account = homebox_test_account
    key = homebox_key_factory()
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"
    # Keep personal configuration and provider credentials out of the child process.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HBC_", "OPENAI_", "ANTHROPIC_"))}
    env.update(
        HBC_HOMEBOX_URL=account.server.base_url,
        HBC_HOMEBOX_API_KEY=key.token,
        HBC_LLM_API_KEY="smoke-only-no-provider-call",
        HBC_LLM_MODEL="gpt-5.6-luna",
        HBC_DISABLE_UPDATE_CHECK="true",
        PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src")]),
    )
    headers = {"Authorization": f"Bearer {account.control_token}"}
    with httpx.Client(base_url=account.api_url + "/", headers=headers, trust_env=False, timeout=15) as control:
        types = control.get("entity-types")
        types.raise_for_status()
        location_type = next(row["id"] for row in types.json() if row["isLocation"])
        location = control.post("entities", json={"name": "Smoke storage", "entityTypeId": location_type})
        location.raise_for_status()
        location_id = location.json()["id"]
        log_path = ROOT / "frontend/test-results/fullstack-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), str(port), str(build)],
                cwd=tmp_path,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 40
                with httpx.Client(trust_env=False, timeout=2) as probe:
                    while time.monotonic() < deadline:
                        assert process.poll() is None, f"Companion exited; see {log_path}"
                        try:
                            if probe.get(f"{url}/api/version").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.2)
                    else:
                        pytest.fail(f"Companion did not become ready; see {log_path}")
                browser_env = {**os.environ, "HBC_SMOKE_URL": url}
                result = subprocess.run(
                    [node, str(cli), "test", "--config=tests/fullstack/playwright.config.ts"],
                    cwd=ROOT / "frontend",
                    env=browser_env,
                    timeout=120,
                    check=False,
                )
                assert result.returncode == 0, f"Browser smoke failed; see frontend/test-results and {log_path}"
                listing = control.get("entities", params={"isLocation": "false", "parentIds": location_id})
                listing.raise_for_status()
                items = listing.json()["items"]
                assert len(items) == 1, "Expected one saved item in the isolated location"
                response = control.get(f"entities/{items[0]['id']}")
                response.raise_for_status()
                item = response.json()
                assert item["name"] == "Smoke desk lamp"
                assert item["manufacturer"] == "Smoke Manufacturing"
                assert item["parent"]["id"] == location_id
                assert item["attachments"], "The saved item must include its photo"
                attachment = control.get(f"entities/{item['id']}/attachments/{item['attachments'][0]['id']}")
                attachment.raise_for_status()
                assert attachment.content
                assert attachment.headers["content-type"].startswith("image/")
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    import uvicorn

    from homebox_companion.tools.vision import detector
    from server.app import create_app

    async def fixed_completion(**kwargs):
        """Keep actual image handling and model validation; replace the provider call only."""
        return {"items": [{"name": "Detected lamp", "quantity": 1, "description": "A desk lamp"}]}

    detector.vision_completion = fixed_completion
    uvicorn.run(create_app(static_directory=sys.argv[2]), host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
