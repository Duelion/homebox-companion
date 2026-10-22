"""Unit contracts for the live Homebox fixture infrastructure."""

from __future__ import annotations

import subprocess

import httpx
import pytest
from conftest import HOMEBOX_IMAGES, _register_with_retry, _wait_for_demo_seed


class _RegistrationClient:
    def __init__(self, statuses: list[tuple[int, str | None]]) -> None:
        self._statuses = iter(statuses)
        self.payloads: list[dict[str, str]] = []

    def post(self, url: str, *, json: dict[str, str]) -> httpx.Response:
        self.payloads.append(json)
        status, retry_after = next(self._statuses)
        headers = {"Retry-After": retry_after} if retry_after is not None else {}
        return httpx.Response(status, headers=headers, request=httpx.Request("POST", url))


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.delays: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.delays.append(delay)
        self.now += delay


def test_supported_homebox_images_are_digest_pinned() -> None:
    prefix = "ghcr.io/sysadminsmedia/homebox@sha256:"
    assert set(HOMEBOX_IMAGES) == {"0.27.0", "0.26.2"}
    assert HOMEBOX_IMAGES["0.27.0"] == prefix + "d49f12caf25ce3fa7f44102bb74953f3dff2dfdad38d87bd9057f3f611e797bb"
    assert HOMEBOX_IMAGES["0.26.2"] == prefix + "b1ad7e3c63f732a5f6daa466e8116be4f545b3b120383a64dcb62beb00a660cc"


def test_registration_retries_only_429_with_same_payload_and_retry_after() -> None:
    client = _RegistrationClient([(429, "3"), (429, "0.5"), (204, None)])
    clock = _FakeClock()
    payload = {"name": "Test", "email": "test@example.invalid", "password": "secret"}

    response = _register_with_retry(
        client, "https://homebox.test/register", payload, sleep=clock.sleep, monotonic=clock.monotonic
    )

    assert response.status_code == 204
    assert clock.delays == [3.0, 0.5]
    assert client.payloads == [payload, payload, payload]
    assert all(sent is payload for sent in client.payloads)


def test_registration_does_not_retry_other_failures() -> None:
    client = _RegistrationClient([(503, "10")])
    clock = _FakeClock()

    response = _register_with_retry(
        client, "https://homebox.test/register", {}, sleep=clock.sleep, monotonic=clock.monotonic
    )

    assert response.status_code == 503
    assert clock.delays == []
    assert len(client.payloads) == 1


def test_registration_retry_is_bounded() -> None:
    client = _RegistrationClient([(429, "1")] * 4)
    clock = _FakeClock()

    response = _register_with_retry(
        client, "https://homebox.test/register", {}, sleep=clock.sleep, monotonic=clock.monotonic
    )

    assert response.status_code == 429
    assert clock.delays == [1.0, 1.0, 1.0]
    assert len(client.payloads) == 4


def test_registration_retry_wait_budget_and_invalid_delay_are_bounded() -> None:
    clock = _FakeClock()
    client = _RegistrationClient([(429, "nan"), (429, "121"), (204, None)])

    response = _register_with_retry(
        client,
        "https://homebox.test/register",
        {},
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        max_wait=180,
    )

    assert response.status_code == 429
    assert clock.delays == [60.0]
    assert len(client.payloads) == 2


def test_demo_seed_gate_waits_for_completion_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = iter(
        [
            subprocess.CompletedProcess([], 0, "starting", ""),
            subprocess.CompletedProcess([], 0, "true running 0", ""),
            subprocess.CompletedProcess([], 0, "Demo setup complete", ""),
        ]
    )
    clock = _FakeClock()
    monkeypatch.setattr("conftest.subprocess.run", lambda *args, **kwargs: next(calls))

    _wait_for_demo_seed("homebox-test", sleep=clock.sleep, monotonic=clock.monotonic)

    assert clock.delays == [0.5]


def test_demo_seed_gate_fails_promptly_when_container_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = iter(
        [
            subprocess.CompletedProcess([], 0, "partial seed log", ""),
            subprocess.CompletedProcess([], 0, "false exited 1", ""),
        ]
    )
    monkeypatch.setattr("conftest.subprocess.run", lambda *args, **kwargs: next(calls))

    with pytest.raises(pytest.fail.Exception, match="exited before demo setup completed"):
        _wait_for_demo_seed("homebox-test", sleep=lambda _: None)
