"""Demo Data Seeder for Homebox.

This script creates the demo user, locations, and sample items
with placeholder images for the public demo deployment.

Run: python -m demo.seed_demo
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx

# Configuration from environment
HOMEBOX_URL = os.getenv("HBC_HOMEBOX_URL", "http://localhost:7745")
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@example.com")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo")
DEMO_NAME = "Demo User"

# Asset directory (relative to this file)
ASSETS_DIR = Path(__file__).parent / "assets"


async def register_user(client: httpx.AsyncClient) -> bool:
    """Register the demo user. Returns True if successful or already exists."""
    print(f"[seed] Registering demo user: {DEMO_EMAIL}")
    try:
        response = await client.post(
            f"{HOMEBOX_URL}/api/v1/users/register",
            json={
                "email": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
                "name": DEMO_NAME,
            },
        )
        # Homebox returns 204 No Content for successful registration
        if response.status_code in (200, 201, 204):
            print("[seed] Demo user registered successfully")
            return True
        elif response.status_code == 409:
            print("[seed] Demo user already exists")
            return True
        else:
            print(f"[seed] Registration failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[seed] Registration error: {e}")
        return False


async def login(client: httpx.AsyncClient) -> str | None:
    """Login and return the auth token."""
    print(f"[seed] Logging in as {DEMO_EMAIL}")
    try:
        response = await client.post(
            f"{HOMEBOX_URL}/api/v1/users/login",
            json={
                "username": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
            },
        )
        if response.status_code == 200:
            data = response.json()
            # Debug: print response structure
            print(f"[seed] Login response keys: {list(data.keys())}")
            # Try different possible token field names
            token = data.get("token") or data.get("accessToken") or data.get("access_token")
            if not token and "attachmentToken" in data:
                # Homebox v0.10+ uses this structure
                token = data.get("token")
            if token:
                print(f"[seed] Login successful, token length: {len(token)}")
                return token
            else:
                print(f"[seed] Login response missing token field: {data}")
                return None
        else:
            print(f"[seed] Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"[seed] Login error: {e}")
        return None


async def create_location(
    client: httpx.AsyncClient,
    token: str,
    name: str,
    description: str = "",
    parent_id: str | None = None,
) -> str | None:
    """Create a location and return its ID."""
    payload = {"name": name, "description": description}
    if parent_id:
        payload["parentId"] = parent_id

    response = await client.post(
        f"{HOMEBOX_URL}/api/v1/locations",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    if response.status_code in (200, 201):
        loc = response.json()
        print(f"[seed] Created location: {name} (ID: {loc['id']})")
        return loc["id"]
    else:
        print(f"[seed] Failed to create location {name}: {response.status_code}")
        return None


async def create_item(
    client: httpx.AsyncClient,
    token: str,
    name: str,
    location_id: str,
    description: str = "",
    quantity: int = 1,
) -> str | None:
    """Create an item and return its ID."""
    response = await client.post(
        f"{HOMEBOX_URL}/api/v1/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "description": description,
            "locationId": location_id,
            "quantity": quantity,
        },
    )
    if response.status_code in (200, 201):
        item = response.json()
        print(f"[seed] Created item: {name} (ID: {item['id']})")
        return item["id"]
    else:
        print(f"[seed] Failed to create item {name}: {response.status_code}")
        return None


async def upload_item_attachment(
    client: httpx.AsyncClient,
    token: str,
    item_id: str,
    image_path: Path,
) -> bool:
    """Upload an image as an attachment to an item."""
    if not image_path.exists():
        print(f"[seed] Image not found: {image_path}")
        return False

    with open(image_path, "rb") as f:
        files = {"file": (image_path.name, f, "image/png")}
        response = await client.post(
            f"{HOMEBOX_URL}/api/v1/items/{item_id}/attachments",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data={"type": "photo", "name": image_path.stem},
        )

    if response.status_code in (200, 201):
        print(f"[seed] Uploaded attachment for item {item_id}")
        return True
    else:
        print(f"[seed] Failed to upload attachment: {response.status_code}")
        return False


# Demo data structure
DEMO_LOCATIONS = [
    {
        "name": "🏠 House",
        "description": "Main family home",
        "children": [
            {"name": "Living Room", "description": "Main living area with entertainment setup"},
            {"name": "Kitchen", "description": "Cooking and dining area"},
            {"name": "Bedroom", "description": "Master bedroom"},
            {"name": "Garage", "description": "Car storage and workshop"},
        ],
    },
    {
        "name": "📦 Storage",
        "description": "Off-site storage unit",
        "children": [
            {"name": "Boxes", "description": "Cardboard boxes with misc items"},
            {"name": "Shelves", "description": "Metal shelving units"},
        ],
    },
]

DEMO_ITEMS = [
    # Living Room items
    {"name": "Samsung Smart TV", "location": "Living Room", "description": "55-inch 4K Smart TV", "image": "smart_tv.png"},
    {"name": "PlayStation 5", "location": "Living Room", "description": "Gaming console with controllers", "image": "gaming_console.png"},
    # Kitchen items
    {"name": "KitchenAid Mixer", "location": "Kitchen", "description": "Stand mixer, red color", "image": "stand_mixer.png"},
    {"name": "Instant Pot", "location": "Kitchen", "description": "6-quart pressure cooker", "image": "instant_pot.png"},
    # Garage items
    {"name": "DeWalt Power Drill", "location": "Garage", "description": "20V cordless drill with battery", "image": "power_drill.png"},
    {"name": "Craftsman Toolbox", "location": "Garage", "description": "Red metal toolbox with assorted tools", "image": "toolbox.png"},
    # IoT Sensors
    {"name": "Zigbee Temperature Sensor", "location": "Living Room", "description": "Aqara temperature and humidity sensor", "image": "temp_sensor.png"},
    {"name": "Smart Motion Sensor", "location": "Bedroom", "description": "Philips Hue motion sensor with light detection", "image": "motion_sensor.png"},
]


async def seed_demo_data():
    """Main seeding function."""
    print("[seed] Starting demo data seeding...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register and login
        if not await register_user(client):
            print("[seed] Failed to register user, aborting")
            sys.exit(1)

        token = await login(client)
        if not token:
            print("[seed] Failed to login, aborting")
            sys.exit(1)

        # Create locations and track IDs by name
        location_ids: dict[str, str] = {}
        
        for loc_data in DEMO_LOCATIONS:
            parent_id = await create_location(
                client, token, loc_data["name"], loc_data.get("description", "")
            )
            if parent_id:
                location_ids[loc_data["name"]] = parent_id
                
                # Create children
                for child in loc_data.get("children", []):
                    child_id = await create_location(
                        client,
                        token,
                        child["name"],
                        child.get("description", ""),
                        parent_id=parent_id,
                    )
                    if child_id:
                        location_ids[child["name"]] = child_id

        # Create items
        for item_data in DEMO_ITEMS:
            loc_name = item_data["location"]
            loc_id = location_ids.get(loc_name)
            if not loc_id:
                print(f"[seed] Location not found for item: {item_data['name']}")
                continue

            item_id = await create_item(
                client,
                token,
                item_data["name"],
                loc_id,
                item_data.get("description", ""),
            )

            # Upload image if available
            if item_id and item_data.get("image"):
                image_path = ASSETS_DIR / item_data["image"]
                await upload_item_attachment(client, token, item_id, image_path)

    print("[seed] Demo data seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
