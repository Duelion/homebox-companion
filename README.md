# homebox

A human-friendly Python library for Homebox inventory management.

**homebox** provides a clean, Pythonic interface for interacting with the [Homebox](https://github.com/hay-kot/homebox) API, plus AI-powered item detection from images. Think of it as `requests` for inventory management.

## ✨ Features

- **Pythonic API** — Clean, intuitive interface inspired by `requests`
- **AI Vision** — Detect items in photos using OpenAI's vision models
- **Smart Logging** — Built-in logging with [loguru](https://github.com/Delgan/loguru)
- **Context Managers** — Automatic session handling with `with` statements
- **Type Hints** — Full type annotations for IDE support
- **Demo Ready** — Works out-of-the-box with Homebox demo environment

## 🚀 Quick Start

### Installation

```bash
uv add homebox
# or
pip install homebox
```

### Basic Usage

```python
import homebox

# Connect to Homebox (uses demo credentials by default)
with homebox.Session() as hb:
    # List locations
    for location in hb.locations():
        print(f"📍 {location.name}")

    # Create an item
    item = hb.create_item(
        "Hammer",
        quantity=2,
        description="Claw hammer with wooden handle",
        location=hb.locations()[0],
    )
    print(f"✅ Created: {item.name} (id: {item.id})")
```

### AI-Powered Detection

Detect items in photos using OpenAI's vision models:

```python
import homebox

# Detect items in an image
items = homebox.detect("tools.jpg")

for item in items:
    print(f"Found: {item.name} x{item.quantity}")
    # Found: Hammer x2
    # Found: Screwdriver x5

# Create detected items in Homebox
with homebox.Session() as hb:
    location = hb.locations()[0]
    for item in items:
        created = hb.create_item(item, location=location)
        print(f"Created: {created.name}")
```

## 📖 Usage Guide

### Sessions

The `Session` class manages authentication and provides methods for all API operations:

```python
import homebox

# Option 1: Context manager (recommended)
with homebox.Session() as hb:
    items = hb.items()

# Option 2: Manual management
hb = homebox.Session()
hb.login()
items = hb.items()
hb.close()

# Option 3: Custom credentials
hb = homebox.Session(
    url="https://my-homebox.example.com/api/v1",
    email="me@example.com",
    password="secret",
)
```

### Working with Items

```python
with homebox.Session() as hb:
    # List all items
    items = hb.items()

    # Get a specific item
    item = hb.item("item-id-123")

    # Create an item
    item = hb.create_item(
        "Screwdriver Set",
        quantity=1,
        description="Phillips and flathead",
        location="location-id",  # or pass a Location object
        labels=["tools", "garage"],  # or pass Label objects
    )

    # Update an item (with typed parameters)
    updated = hb.update_item(
        "item-id",
        name="New Name",
        quantity=5,
        description="Updated description",
    )

    # Update purchase info
    hb.update_item(
        "item-id",
        purchase_from="Amazon",
        purchase_price=29.99,
        purchase_time="2024-01-15",
    )

    # Update warranty info
    hb.update_item(
        "item-id",
        lifetime_warranty=False,
        warranty_expires="2026-01-15",
        warranty_details="2-year manufacturer warranty",
    )

    # Archive/unarchive items
    hb.archive_item("item-id")
    hb.unarchive_item("item-id")

    # Delete an item
    hb.delete_item("item-id")
```

### Locations and Labels

```python
with homebox.Session() as hb:
    # List all locations
    locations = hb.locations()
    for loc in locations:
        print(f"{loc.name}: {loc.item_count} items")

    # List all labels
    labels = hb.labels()
    for label in labels:
        print(f"🏷️ {label.name}")
```

### AI Vision Detection

```python
import homebox

# Simple one-liner
items = homebox.detect("photo.jpg")

# With custom settings
items = homebox.detect(
    "photo.jpg",
    api_key="sk-...",  # or set OPENAI_API_KEY env var
    model="gpt-4o",  # default: gpt-4o-mini
)

# Using VisionClient for multiple images
vision = homebox.VisionClient(model="gpt-4o")
items1 = vision.detect("photo1.jpg")
items2 = vision.detect("photo2.jpg")
```

### Logging

homebox uses [loguru](https://github.com/Delgan/loguru) for beautiful, configurable logging:

```python
import homebox

# Set log level
homebox.configure(level="DEBUG")

# Access the logger directly
homebox.logger.info("Custom message")

# Disable logging
homebox.configure(level="CRITICAL")
```

## 🔧 Development Setup

```bash
# Clone the repo
git clone https://github.com/your-org/homebox-py
cd homebox-py

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Run linting
uv run ruff check .

# Run tests
uv run pytest

# Run integration tests (requires OPENAI_API_KEY)
uv run pytest -m integration
```

## 📚 API Reference

### Core Classes

| Class | Description |
|-------|-------------|
| `Session` | Main API client with authentication |
| `Item` | Inventory item data structure |
| `Location` | Storage location |
| `Label` | Item tag/label |
| `VisionClient` | AI-powered item detection |

### Top-Level Functions

| Function | Description |
|----------|-------------|
| `detect(image)` | Detect items in an image using AI |
| `configure(level=...)` | Configure logging |
| `encode_image(path)` | Encode image as base64 data URI |

### Exceptions

| Exception | Description |
|-----------|-------------|
| `HomeboxError` | Base exception for API errors |
| `AuthenticationError` | Login/auth failures |

## 🔗 Links

- [Homebox](https://github.com/hay-kot/homebox) — Self-hosted inventory management
- [Demo Instance](https://demo.homebox.software) — Try it out (demo@example.com / demo)

## 📄 License

MIT
