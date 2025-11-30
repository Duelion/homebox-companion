"""Create an item in the Homebox demo environment."""
from __future__ import annotations

from datetime import UTC, datetime

from homebox_demo_adapter import DetectedItem, HomeboxDemoAdapter


def pick_first_location_id(client: HomeboxDemoAdapter, token: str) -> str:
    response = client.session.get(
        f"{client.base_url}/locations",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    client._ensure_success(response, "Fetch locations")
    locations = response.json()
    if not locations:
        raise RuntimeError("No locations available in the demo account.")
    return locations[0]["id"]


def main() -> None:
    client = HomeboxDemoAdapter()
    token = client.login()
    location_id = pick_first_location_id(client, token)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    item = DetectedItem(
        name=f"Demo API item {timestamp}",
        quantity=1,
        description="Created via automation script.",
        location_id=location_id,
    )
    created = client.create_items(token, [item])[0]
    print(f"Created item '{created.get('name')}' with id {created.get('id')}")


if __name__ == "__main__":
    main()
