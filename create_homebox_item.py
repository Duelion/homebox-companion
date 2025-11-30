"""Create an item in the Homebox demo environment.

This script demonstrates the clean, Pythonic API of the homebox library.
"""
from __future__ import annotations

from datetime import UTC, datetime

import homebox


def main() -> None:
    """Create a demo item using the new Session API."""
    # Enable debug logging to see what's happening
    homebox.configure(level="INFO")

    # Use Session as a context manager for automatic auth
    with homebox.Session() as hb:
        # Get locations
        locations = hb.locations()
        if not locations:
            raise RuntimeError("No locations available in the demo account.")

        location = locations[0]
        print(f"Using location: {location.name}")

        # Create an item
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        item = hb.create_item(
            f"Demo API item {timestamp}",
            quantity=1,
            description="Created via automation script.",
            location=location,
        )

        print(f"Created item '{item.name}' with id {item.id}")


if __name__ == "__main__":
    main()
