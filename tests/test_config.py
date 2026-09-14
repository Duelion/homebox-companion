"""Tests for the /api/config endpoint."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    import server.api.config as config_module

    app = FastAPI()
    app.include_router(config_module.router, prefix="/api")
    return TestClient(app)


class TestLinkBaseUrl:
    """link_base_url should only be exposed when HBC_LINK_BASE_URL is explicitly set."""

    def _get(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
        import server.api.config as config_module

        monkeypatch.setattr(config_module.settings, "homebox_url", "http://10.0.0.5:7745")
        return client.get("/api/config").json()

    def test_link_base_url_none_when_not_configured(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        import server.api.config as config_module

        monkeypatch.setattr(config_module.settings, "link_base_url", "")
        body = self._get(client, monkeypatch)
        assert body["homebox_url"] == "http://10.0.0.5:7745"
        assert body["link_base_url"] is None

    def test_link_base_url_exposed_when_configured(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        import server.api.config as config_module

        public = "https://inventory.example.com"
        monkeypatch.setattr(config_module.settings, "link_base_url", public)
        body = self._get(client, monkeypatch)
        # homebox_url still prefers the public link base for user-facing links
        assert body["homebox_url"] == public
        assert body["link_base_url"] == public
