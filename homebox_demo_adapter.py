"""Adapter for working with the Homebox demo API and vision-based item extraction."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import requests
from openai import OpenAI

DEMO_BASE_URL = "https://demo.homebox.software/api/v1"

# Reuse the browser-style headers to avoid being blocked by network protections.
DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://demo.homebox.software",
    "Referer": "https://demo.homebox.software/",
    "Connection": "keep-alive",
    "DNT": "1",
    "Sec-GPC": "1",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}


@dataclass
class DetectedItem:
    """Structured representation for objects found in an image."""

    name: str
    quantity: int
    description: str | None = None
    location_id: str | None = None
    label_ids: List[str] | None = None

    def as_item_payload(self) -> Dict[str, str | int | List[str]]:
        """Convert the detected item into the payload expected by the API.

        The API accepts names up to 255 characters and descriptions up to 1000
        characters. Values are clamped to stay within those limits.
        """

        name = (self.name or "Untitled item").strip()
        name = name[:255] if len(name) > 255 else name

        description = (self.description or "Created via OpenAI vision analysis.").strip()
        if len(description) > 1000:
            description = description[:1000]

        payload: Dict[str, str | int | List[str]] = {
            "name": name,
            "description": description,
            "quantity": max(int(self.quantity or 1), 1),
        }

        if self.location_id:
            payload["locationId"] = self.location_id
        if self.label_ids:
            payload["labelIds"] = self.label_ids
        return payload


class HomeboxDemoAdapter:
    """Minimal client for the Homebox demo environment."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.base_url = DEMO_BASE_URL

    def login(self, username: str = "demo@example.com", password: str = "demo") -> str:
        payload = {
            "username": username,
            "password": password,
            "stayLoggedIn": True,
        }
        response = self.session.post(
            f"{self.base_url}/users/login",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
            timeout=20,
        )
        self._ensure_success(response, "Login")
        data = response.json()
        token = data.get("token") or data.get("jwt") or data.get("accessToken")
        if not token:
            raise RuntimeError("Login response did not include a token field.")
        return token

    def create_items(self, token: str, items: Iterable[DetectedItem]) -> List[dict]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        created: List[dict] = []
        for item in items:
            response = self.session.post(
                f"{self.base_url}/items",
                headers=headers,
                json=item.as_item_payload(),
                timeout=20,
            )
            self._ensure_success(response, "Create item")
            created.append(response.json())
        return created

    @staticmethod
    def _ensure_success(response: requests.Response, context: str) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise RuntimeError(f"{context} failed with {response.status_code}: {detail}") from exc


def encode_image_to_data_uri(image_path: Path) -> str:
    """Read the image and return a data URI suitable for OpenAI's vision API."""

    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/{suffix};base64,{payload}"


def detect_items_with_openai(
    image_path: Path,
    api_key: str,
    model: str = "gpt-4o-mini",
) -> List[DetectedItem]:
    """Use an OpenAI vision model to detect items and quantities in an image."""

    data_uri = encode_image_to_data_uri(image_path)
    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an inventory assistant for the Homebox API. "
                    "Return a single JSON object with an `items` array. Each item must "
                    "include: `name` (<=255 characters), integer `quantity` (>=1), and "
                    "optional `description` (<=1000 characters) summarizing condition or "
                    "notable attributes. Combine identical objects into a single entry "
                    "with the correct quantity. Do not add extra commentary."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "List all distinct items visible in this image. Return only JSON. "
                            "Example format: {\"items\":[{\"name\":\"hammer\",\"quantity\":2,"
                            "\"description\":\"Steel head with wooden handle\"}]}."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
    )
    message = completion.choices[0].message
    raw_content = message.content or "{}"
    parsed_content = getattr(message, "parsed", None) or json.loads(raw_content)
    detected = []
    for item in parsed_content.get("items", []):
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        quantity_raw = item.get("quantity", 1)
        try:
            quantity = int(quantity_raw)
        except (TypeError, ValueError):
            quantity = 1
        description = item.get("description")
        detected.append(
            DetectedItem(
                name=name,
                quantity=quantity,
                description=description,
            )
        )
    return detected


__all__ = [
    "DetectedItem",
    "HomeboxDemoAdapter",
    "detect_items_with_openai",
    "encode_image_to_data_uri",
]
