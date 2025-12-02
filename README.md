# Homebox Companion

🏠📸 **AI-powered companion app for [Homebox](https://github.com/sysadminsmedia/homebox) inventory management.**

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
- Node.js 18+ (for frontend development)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- A Homebox instance (or use the demo server)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/homebox-companion.git
cd homebox-companion

# Install Python dependencies
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### Configuration

Set the required environment variables:

**Linux/macOS:**
```bash
# Required: Your OpenAI API key
export HBC_OPENAI_API_KEY="sk-your-api-key-here"

# Required: Your Homebox API URL
export HBC_API_URL="https://your-homebox.example.com/api/v1"

# Optional: OpenAI model (default: gpt-4o-mini)
export HBC_OPENAI_MODEL="gpt-4o-mini"

# Optional: Server configuration
export HBC_SERVER_HOST="0.0.0.0"
export HBC_SERVER_PORT="8000"

# Optional: Log level (DEBUG, INFO, WARNING, ERROR)
export HBC_LOG_LEVEL="INFO"
```

**Windows (PowerShell):**
```powershell
$env:HBC_OPENAI_API_KEY = "sk-your-api-key-here"
$env:HBC_API_URL = "https://your-homebox.example.com/api/v1"
```

### Running the App

**Development (both backend and frontend):**

```bash
# Terminal 1: Start backend
uv run uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend dev server
cd frontend && npm run dev
```

Open `http://localhost:5173` in your browser.

**Production:**

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Start server
uv run python -m server.app
```

## Environment Variables Reference

All environment variables use the `HBC_` prefix (short for Homebox Companion).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HBC_OPENAI_API_KEY` | ✅ Yes | - | Your OpenAI API key |
| `HBC_API_URL` | ✅ Yes | Demo server | Your Homebox API URL |
| `HBC_OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model for vision |
| `HBC_SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `HBC_SERVER_PORT` | No | `8000` | Server port |
| `HBC_LOG_LEVEL` | No | `INFO` | Logging level |

## Usage

1. **Login** – Enter your Homebox credentials
2. **Select Location** – Navigate your location hierarchy to choose where items will be stored
3. **Capture/Upload Photo** – Take or upload a photo of items
4. **Review Detection** – AI identifies items in the image
5. **Edit & Confirm** – Adjust names, quantities, labels as needed
6. **Save to Homebox** – Items are created in your inventory

## Using with Demo Server

For testing, you can use the Homebox demo server:

```bash
export HBC_API_URL="https://demo.homebox.software/api/v1"
```

Demo credentials: `demo@example.com` / `demo`

## Project Structure

```
homebox-companion/
├── src/
│   └── homebox_companion/          # Python package
│       ├── core/                   # Config, logging, exceptions
│       ├── homebox/                # Homebox API client
│       ├── ai/                     # OpenAI integration
│       └── tools/                  # AI tools (vision, etc.)
│           └── vision/             # Item detection
├── server/                         # FastAPI backend
│   ├── app.py                      # App factory
│   ├── api/                        # API routers
│   └── schemas/                    # Pydantic models
├── frontend/                       # Svelte + Tailwind frontend
│   └── src/
│       ├── lib/                    # Stores, API client
│       └── routes/                 # Pages
├── tests/                          # Test suite
├── pyproject.toml                  # Python config
└── AGENTS.md                       # AI agent guidelines
```

## Development

### Linting

```bash
uv run ruff check .
uv run ruff format .
```

### Testing

```bash
# Run unit tests
uv run pytest

# Run integration tests (requires API keys)
uv run pytest -m integration
```

### Frontend Development

```bash
cd frontend
npm run dev      # Start dev server
npm run build    # Production build
npm run preview  # Preview production build
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` | Authenticate with Homebox |
| GET | `/api/locations` | List all locations |
| GET | `/api/locations/tree` | Get hierarchical location tree |
| GET | `/api/locations/{id}` | Get single location details |
| GET | `/api/labels` | List all labels |
| POST | `/api/items` | Batch create items |
| POST | `/api/items/{id}/attachments` | Upload item attachment |
| POST | `/api/tools/vision/detect` | Detect items in image |
| POST | `/api/tools/vision/analyze` | Multi-image analysis |
| POST | `/api/tools/vision/merge` | Merge items using AI |
| POST | `/api/tools/vision/correct` | Correct item with feedback |

## Library Usage

The `homebox_companion` package can also be used as a Python library:

```python
from homebox_companion import detect_items_from_bytes, HomeboxClient

# Detect items in an image (async)
items = await detect_items_from_bytes(image_bytes)
for item in items:
    print(f"{item.name}: {item.quantity}")

# Create items in Homebox
async with HomeboxClient() as client:
    token = await client.login("user@example.com", "password")
    locations = await client.list_locations(token)
    
    for item in items:
        await client.create_item(token, ItemCreate(
            name=item.name,
            quantity=item.quantity,
            description=item.description,
            location_id=locations[0]["id"],
        ))
```

## Contributing

Contributions are welcome! Please ensure:

1. Code passes `ruff check .`
2. Tests pass with `pytest`
3. Increment version in `pyproject.toml`

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Homebox](https://github.com/sysadminsmedia/homebox) - The excellent home inventory system this companion is built for
- [OpenAI](https://openai.com) - For the vision AI capabilities
- [FastAPI](https://fastapi.tiangolo.com) - The modern Python web framework
- [SvelteKit](https://kit.svelte.dev) - The elegant frontend framework
- [Tailwind CSS](https://tailwindcss.com) - The utility-first CSS framework
