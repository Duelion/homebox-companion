"""Create an item in the Homebox demo environment."""
from __future__ import annotations

from datetime import UTC, datetime

from homebox import DetectedItem, HomeboxDemoClient


def pick_first_location_id(client: HomeboxDemoClient, token: str) -> str:
    locations = client.list_locations(token)
    if not locations:
        raise RuntimeError("No locations available in the demo account.")
    return locations[0]["id"]


def main() -> None:
    client = HomeboxDemoClient()
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
