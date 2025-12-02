# Homebox Vision Companion

🏠📸 **AI-powered item detection for [Homebox](https://github.com/sysadminsmedia/homebox) inventory management.**

Take a photo of your stuff, and let AI identify and catalog items directly into your Homebox instance. Perfect for quickly inventorying a room, shelf, or collection.

## Features

- 📷 **Photo-based Detection** – Upload or capture photos of items
- 🤖 **AI Vision Analysis** – Uses OpenAI GPT-4o to identify items in images
- 🏷️ **Smart Labeling** – Automatically suggests labels from your Homebox labels
- 📍 **Hierarchical Locations** – Navigate your location tree to place items
- ✏️ **Review & Edit** – Edit AI suggestions before saving
- 🔀 **Merge Items** – Combine multiple detected items into one
- 🔧 **AI Corrections** – Tell the AI what it got wrong and it will fix it
- 📱 **Mobile-First UI** – Designed for phones (works on desktop too)

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- A Homebox instance (or use the demo server)
- Node.js 18+ (for frontend development)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/homebox-vision.git
cd homebox-vision

# Create virtual environment and install dependencies
uv venv
uv sync

# Or with pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Configuration

Set the required environment variables:

**Linux/macOS:**
```bash
# Required: Your OpenAI API key
export HOMEBOX_VISION_OPENAI_API_KEY="sk-your-api-key-here"

# Required: Your Homebox API URL
export HOMEBOX_VISION_API_URL="https://your-homebox.example.com/api/v1"

# Optional: OpenAI model (default: gpt-5-mini)
export HOMEBOX_VISION_OPENAI_MODEL="gpt-5-mini"

# Optional: Server configuration
export HOMEBOX_VISION_SERVER_HOST="0.0.0.0"
export HOMEBOX_VISION_SERVER_PORT="8000"

# Optional: Log level (DEBUG, INFO, WARNING, ERROR)
export HOMEBOX_VISION_LOG_LEVEL="INFO"
```

**Windows (PowerShell):**
```powershell
$env:HOMEBOX_VISION_OPENAI_API_KEY = "sk-your-api-key-here"
$env:HOMEBOX_VISION_API_URL = "https://your-homebox.example.com/api/v1"
```

### Running the App

```bash
# Using uv
uv run python -m server.main

# Or with the CLI command (after pip install -e .)
homebox-vision

# Or with uvicorn directly
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

## Environment Variables Reference

All environment variables use the `HOMEBOX_VISION_` prefix to avoid conflicts with other applications.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HOMEBOX_VISION_OPENAI_API_KEY` | ✅ Yes | - | Your OpenAI API key |
| `HOMEBOX_VISION_API_URL` | ✅ Yes | Demo server | Your Homebox API URL |
| `HOMEBOX_VISION_OPENAI_MODEL` | No | `gpt-5-mini` | OpenAI model for vision |
| `HOMEBOX_VISION_SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `HOMEBOX_VISION_SERVER_PORT` | No | `8000` | Server port |
| `HOMEBOX_VISION_LOG_LEVEL` | No | `INFO` | Logging level |

## Usage

1. **Login** – Enter your Homebox credentials
2. **Select Location** – Navigate your location hierarchy to choose where items will be stored
3. **Capture/Upload Photo** – Take or upload a photo of items
4. **Review Detection** – AI identifies items in the image
5. **Edit & Confirm** – Adjust names, quantities, labels as needed
   - Use **Merge** to combine similar items
   - Use **Correct** to tell the AI what it got wrong
6. **Save to Homebox** – Items are created in your inventory

## Using with Demo Server

For testing, you can use the Homebox demo server:

```bash
export HOMEBOX_VISION_API_URL="https://demo.homebox.software/api/v1"
```

Demo credentials: `demo@example.com` / `demo`

## Architecture

The application follows a modular architecture designed for maintainability and future extensibility.

### Backend (Python/FastAPI)

The backend uses a modular router-based architecture with a service layer:

```
server/
├── main.py              # App factory & configuration
├── dependencies.py      # Shared FastAPI dependencies
├── routers/             # Feature-based API routers
│   ├── auth.py          # Authentication
│   ├── locations.py     # Location management
│   ├── labels.py        # Label retrieval
│   ├── detection.py     # AI detection (detect, analyze, merge, correct)
│   └── items.py         # Item creation & attachments
├── schemas/             # Pydantic request/response models
│   ├── auth.py
│   ├── items.py
│   └── detection.py
└── services/            # Business logic & external API orchestration
    ├── ai_service.py    # OpenAI operations
    └── homebox_service.py  # Homebox API operations
```

### Frontend (React/TypeScript)

The frontend is a modern React SPA with predictable state management:

```
frontend/
├── src/
│   ├── api/             # API client with retry/backoff
│   │   ├── client.ts    # HTTP client
│   │   └── types.ts     # TypeScript interfaces
│   ├── store/           # Zustand state management
│   │   └── index.ts     # Wizard flow state
│   ├── components/
│   │   ├── ui/          # Button, Input, Toast, Loader, etc.
│   │   ├── layout/      # AppShell, Header, Footer
│   │   └── features/    # Login, LocationPicker, ImageCapture, etc.
│   └── hooks/           # useToast, useOnlineStatus
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

### Core Library

The `homebox_vision` package provides reusable utilities:

```
homebox_vision/
├── client.py    # Sync & async Homebox API clients
├── llm.py       # OpenAI vision integration
├── models.py    # Data models (DetectedItem)
└── config.py    # Configuration management
```

## Development

### Backend Development

```bash
# Install dependencies
uv sync

# Run with hot reload
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

# Linting
uv run ruff check .
uv run ruff format .

# Testing
uv run pytest
uv run pytest -m integration  # Requires API keys
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api to backend at :8000)
npm run dev

# Build for production (outputs to server/static/)
npm run build

# Type checking
npm run typecheck

# Linting
npm run lint
```

### Project Structure

```
homebox-vision/
├── homebox_vision/          # Core Python library
│   ├── __init__.py          # Public API exports
│   ├── client.py            # Homebox API client (sync + async)
│   ├── config.py            # Configuration management
│   ├── llm.py               # OpenAI vision integration
│   └── models.py            # Data models
├── server/                   # FastAPI backend (modular)
│   ├── main.py              # App factory
│   ├── dependencies.py      # Shared dependencies
│   ├── routers/             # API route handlers
│   ├── schemas/             # Pydantic models
│   ├── services/            # Business logic
│   └── static/              # Built frontend assets
├── frontend/                 # React + TypeScript SPA
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── tests/                    # Test suite
├── pyproject.toml           # Python project config
└── README.md                # This file
```

## Library Usage

The `homebox_vision` package can also be used as a Python library:

```python
from homebox_vision import detect_items, HomeboxClient

# Detect items in an image (sync - great for scripts)
items = detect_items("photo.jpg")
for item in items:
    print(f"{item.name}: {item.quantity}")

# Create items in Homebox
with HomeboxClient(base_url="https://your-homebox/api/v1") as client:
    token = client.login("user@example.com", "password")
    locations = client.list_locations(token)
    
    for item in items:
        item.location_id = locations[0]["id"]
        client.create_item(token, item)
```

### Available Functions

```python
from homebox_vision import (
    # Configuration
    settings,
    
    # Clients (sync and async)
    HomeboxClient,
    AsyncHomeboxClient,
    
    # Models
    DetectedItem,
    
    # Detection functions
    detect_items,              # Sync - detect from file path (for scripts)
    detect_items_from_bytes,   # Async - detect from raw bytes (for servers)
    
    # Advanced AI functions (all async)
    analyze_item_details_from_images,  # Multi-image detailed analysis
    merge_items_with_openai,           # Combine similar items
    correct_item_with_openai,          # Fix detection with user feedback
    
    # Image encoding utilities
    encode_image_to_data_uri,
    encode_image_bytes_to_data_uri,
)
```

## API Endpoints

The FastAPI backend exposes these endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` | Authenticate with Homebox |
| GET | `/api/locations` | List all locations |
| GET | `/api/locations/tree` | Get hierarchical location tree |
| GET | `/api/locations/{id}` | Get single location details |
| GET | `/api/labels` | List all labels |
| POST | `/api/detect` | Detect items in uploaded image |
| POST | `/api/items` | Batch create items |
| POST | `/api/analyze-advanced` | Multi-image item analysis |
| POST | `/api/merge-items` | Merge items using AI |
| POST | `/api/correct-item` | Correct item with feedback |
| POST | `/api/items/{id}/attachments` | Upload item attachment |
| GET | `/api/version` | Get API version |

## Tech Stack

**Backend:**
- Python 3.12+
- FastAPI with modular routers
- HTTPX for async HTTP client
- OpenAI SDK for vision AI
- Pydantic for data validation
- Loguru for logging

**Frontend:**
- React 18 with TypeScript
- Vite for build tooling
- Tailwind CSS for styling
- Zustand for state management
- Lucide React for icons

## Contributing

Contributions are welcome! Please ensure:

1. Code passes `uv run ruff check .`
2. Tests pass with `uv run pytest`
3. Frontend builds with `cd frontend && npm run build`
4. Increment version in `pyproject.toml`

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Homebox](https://github.com/sysadminsmedia/homebox) - The excellent home inventory system this companion is built for
- [OpenAI](https://openai.com) - For the vision AI capabilities
- [FastAPI](https://fastapi.tiangolo.com) - The modern Python web framework
