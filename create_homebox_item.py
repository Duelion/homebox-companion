"""Script to create a Homebox item using the production API."""
import os
from datetime import datetime
from typing import Dict

import requests

BASE_URL = "https://homebox.duelion.com/api"

# Cloudflare sometimes blocks script-like clients; present ourselves as a modern browser
# and keep a session so cookies (if any) persist across calls.
DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://homebox.duelion.com",
    "Referer": "https://homebox.duelion.com/",
    "Connection": "keep-alive",
    "DNT": "1",
    "Sec-GPC": "1",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

session = requests.Session()
session.headers.update(DEFAULT_HEADERS)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def handle_response(response: requests.Response, context: str) -> requests.Response:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - network dependent
        detail: str
        try:
            detail = response.json()  # type: ignore[assignment]
        except ValueError:
            detail = response.text
        raise SystemExit(f"{context} failed with {response.status_code}: {detail}") from exc
    return response


def login(username: str, password: str) -> str:
    payload = {
        "username": username,
        "password": password,
        "stayLoggedIn": True,
    }
    response = session.post(
        f"{BASE_URL}/v1/users/login",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    data = handle_response(response, "Login").json()
    for key in ("token", "jwt", "accessToken"):
        token = data.get(key)
        if token:
            return token
    raise SystemExit("Login response did not include a token field.")


def create_item(token: str, name: str, description: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "name": name,
        "description": description,
    }
    response = session.post(
        f"{BASE_URL}/v1/items",
        headers=headers,
        json=payload,
        timeout=20,
    )
    return handle_response(response, "Create item").json()


def main() -> None:
    username = require_env("HOMEBOX_USER")
    password = require_env("HOMEBOX_PASS")
    token = login(username, password)
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    item_name = f"API-created item {timestamp}"
    item_description = "Created via automation script."
    created = create_item(token, item_name, item_description)
    print(f"Created item '{created.get('name')}' with id {created.get('id')}")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        raise SystemExit(f"Network error while calling Homebox API: {exc}") from exc
