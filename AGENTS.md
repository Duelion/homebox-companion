# Agent Guidelines

Instructions for AI/LLM agents working on this codebase.

---

## Environment & Tooling

- Target any Homebox instance via the `HOMEBOX_VISION_API_URL` environment variable. For testing, use the **demo** API at `https://demo.homebox.software/api/v1` with demo credentials (`demo@example.com` / `demo`).
- Manage Python tooling with **uv**: create a virtual environment via `uv venv`, add dependencies with `uv add`, and run scripts with `uv run`. Keep dependencies tracked in `pyproject.toml` and `uv.lock`.
- The OpenAI API key is provided via the `HOMEBOX_VISION_OPENAI_API_KEY` environment variable.
- When testing functionality, hit the real demo API and the real OpenAI API rather than mocks or stubs.
- Run `uv run ruff check .` before sending a commit to keep lint feedback consistent.
- Increment the project version number in `pyproject.toml` for every pull request.

---

## Environment Variables

All environment variables use the `HOMEBOX_VISION_` prefix to avoid conflicts with other applications:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HOMEBOX_VISION_OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `HOMEBOX_VISION_API_URL` | Yes | Demo server | Your Homebox API URL |
| `HOMEBOX_VISION_OPENAI_MODEL` | No | `gpt-5-mini` | OpenAI model for vision |
| `HOMEBOX_VISION_SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `HOMEBOX_VISION_SERVER_PORT` | No | `8000` | Server port |
| `HOMEBOX_VISION_LOG_LEVEL` | No | `INFO` | Logging level |

---

## Application Flow

### 1. Login & Token Management
- User logs in to Homebox API via the mobile web app.
- The app obtains a bearer token from the API response.
- Store the bearer token securely on the client (sessionStorage) until it expires.
- When expired, trigger a new login.
- All subsequent API calls must include the bearer token in an `Authorization: Bearer <token>` header.

### 2. Location Selection
- After login, immediately fetch the list of available locations from Homebox via API.
- Present the locations in a hierarchical dropdown menu for the user to select.
- Store the selected location and use it for all subsequent item operations in this session.

### 3. Image Upload / Capture & Item Detection
- Prompt user to upload a photo or take one using the phone camera.
- Send that image to the backend API endpoint.
- Use the existing vision/LLM logic to call OpenAI (with the model and API key defined in environment variables) to detect and generate a list of items present in the image.

### 4. Pre-fill Item Forms for User Review
- For each detected item, render a form on the frontend with pre-filled values (as suggested by the LLM).
- Allow the user to review and edit each item (e.g., name, quantity, description, location, labels).
- Provide the ability to accept, edit, merge, correct, or skip any item.
- Support item corrections via AI when users provide feedback (e.g., "these are actually screwdrivers").
- Support merging multiple items into one when they represent the same thing.
- After confirming one item, proceed to the next; repeat until all items are processed.

### 5. Summary & Final Confirmation
- Once all items have been reviewed (or skipped), present a summary view listing all items that will be submitted, along with their metadata and the chosen location.
- Ask the user for final confirmation.
- Upon confirmation, send a batch request to Homebox API to commit all items under the selected location.

---

## Backend Best Practices (HTTPX)

### HTTP Client Usage
- Use HTTPX `Client` or `AsyncClient` rather than top-level API calls. This enables:
  - Connection pooling
  - Persistent sessions
  - Persistent headers (e.g., auth headers)
  - HTTP/2 support

### Async Operations
- For many asynchronous requests (parallel fetches, LLM calls, bulk API calls), prefer `AsyncClient` to avoid blocking and leverage concurrency.

### Error Handling
- Implement error handling, timeouts, and retries for HTTP requests.
- Don't assume all calls will succeed; detect non-2xx responses or network failures and handle gracefully.

### Token Security
- Manage bearer tokens properly: use secure storage, avoid exposing tokens in unsafe contexts.
- Handle token expiration and refresh (or re-login) when needed.
- Bearer tokens must be treated as sensitive credentials.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Mobile Web Frontend                          │
│  (HTML/CSS/JS - runs in browser)                                │
├─────────────────────────────────────────────────────────────────┤
│  • Login form                                                    │
│  • Hierarchical location picker                                  │
│  • Camera/file upload                                            │
│  • Item review forms with merge/correct                          │
│  • Summary & confirmation                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  (Python - server/main.py)                                      │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/login              → Proxy to Homebox login          │
│  GET  /api/locations          → Fetch locations (flat list)     │
│  GET  /api/locations/tree     → Fetch locations (hierarchical)  │
│  GET  /api/locations/{id}     → Fetch single location details   │
│  GET  /api/labels             → Fetch labels (auth required)    │
│  POST /api/detect             → Upload image, run LLM detection │
│  POST /api/items              → Batch create items in Homebox   │
│  POST /api/analyze-advanced   → Multi-image item analysis       │
│  POST /api/merge-items        → Merge multiple items via AI     │
│  POST /api/correct-item       → Correct item based on feedback  │
│  POST /api/items/{id}/attachments → Upload item attachment      │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────────┐     ┌─────────────────────────┐
│   Homebox Instance          │     │     OpenAI API          │
│   (Self-hosted or demo)     │     │     (Vision/LLM)        │
└─────────────────────────────┘     └─────────────────────────┘
```

---

## Project Structure

```
homebox-vision/
├── homebox_vision/          # Core library
│   ├── __init__.py          # Public API exports
│   ├── client.py            # Homebox API client (sync + async)
│   ├── config.py            # Centralized configuration
│   ├── llm.py               # OpenAI vision integration
│   └── models.py            # Data models (DetectedItem)
├── server/                   # FastAPI web app (modular)
│   ├── __init__.py
│   ├── main.py              # App factory, lifespan, middleware
│   ├── dependencies.py      # Shared FastAPI dependencies
│   ├── routers/             # Feature-based API routers
│   │   ├── auth.py          # Login endpoint
│   │   ├── locations.py     # Location endpoints
│   │   ├── labels.py        # Labels endpoint
│   │   ├── detection.py     # AI detection endpoints
│   │   └── items.py         # Item CRUD endpoints
│   ├── schemas/             # Pydantic request/response models
│   │   ├── auth.py
│   │   ├── items.py
│   │   └── detection.py
│   ├── services/            # Service layer for orchestration
│   │   ├── ai_service.py    # OpenAI operations
│   │   └── homebox_service.py  # Homebox API operations
│   └── static/              # Legacy frontend (backwards compat)
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── frontend/                 # React + TypeScript SPA (new)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/             # API client with retry/backoff
│       │   ├── client.ts
│       │   └── types.ts     # TypeScript API types
│       ├── store/           # Zustand state management
│       │   └── index.ts
│       ├── components/
│       │   ├── ui/          # Reusable UI components
│       │   ├── layout/      # Layout components
│       │   └── features/    # Feature components
│       ├── hooks/           # Custom React hooks
│       └── styles/          # Global CSS
├── tests/                    # Test suite
│   ├── assets/
│   ├── test_client.py
│   ├── test_llm.py
│   └── test_integration.py
├── logs/                     # Application logs (auto-generated)
├── pyproject.toml           # Project configuration
├── uv.lock                  # Dependency lock file
├── AGENTS.md                # This file (LLM instructions)
└── README.md                # User documentation
```

---

## Running the Application

```bash
# Install dependencies
uv sync

# Set required environment variables
export HOMEBOX_VISION_OPENAI_API_KEY="sk-your-key"
export HOMEBOX_VISION_API_URL="https://your-homebox.example.com/api/v1"

# Start the server (default port 8000)
uv run python -m server.main

# Or with the CLI command
homebox-vision

# Or with uvicorn directly (with hot reload for development)
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in a mobile browser or desktop browser with mobile emulation.

---

## Key Library Exports

The `homebox_vision` package exports these primary utilities:

```python
from homebox_vision import (
    # Configuration
    settings,
    
    # Clients (sync and async)
    HomeboxClient,
    AsyncHomeboxClient,
    
    # Data models
    DetectedItem,
    
    # Detection functions
    detect_items,              # Sync - for scripts
    detect_items_from_bytes,   # Async - for servers
    
    # Advanced AI functions (async)
    analyze_item_details_from_images,
    correct_item_with_openai,
    merge_items_with_openai,
    
    # Image encoding
    encode_image_to_data_uri,
    encode_image_bytes_to_data_uri,
)
```

---

## Version Management

Keep versions synchronized across:
- `pyproject.toml` - The source of truth
- `server/main.py` - FastAPI app version (for API docs)
- `homebox_vision/__init__.py` - Package `__version__`
- `frontend/package.json` - Frontend package version
- `server/static/app.js` - Version in file header (legacy)
- `server/static/index.html` - Cache-busting query parameters (legacy)

Increment all locations when releasing a new version.

### Frontend Development

The new React frontend is in the `frontend/` directory:

```bash
# Install frontend dependencies
cd frontend && npm install

# Start Vite dev server (proxies API to backend)
npm run dev

# Build for production (outputs to server/static/)
npm run build
```

The frontend uses:
- **React 18** with TypeScript
- **Vite** for fast development and building
- **Tailwind CSS** for styling
- **Zustand** for state management
- **Lucide React** for icons

### Future Multi-App Support

The architecture is designed to support multiple companion apps via a hamburger menu. When adding new apps:
1. Add a new feature directory under `frontend/src/components/features/`
2. Add new wizard steps to the store
3. The layout/navigation can be extended for app switching
