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
| `HOMEBOX_VISION_OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model for vision |
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

## Backend Architecture

The backend follows a modular architecture with clear separation of concerns:

### Directory Structure

```
server/
├── main.py              # App factory, lifespan, middleware, router includes
├── dependencies.py      # Shared FastAPI dependencies (clients, auth, etc.)
├── routers/             # Feature-based API routers
│   ├── __init__.py      # Router aggregation
│   ├── auth.py          # POST /api/login
│   ├── locations.py     # GET /api/locations, /tree, /{id}
│   ├── labels.py        # GET /api/labels
│   ├── detection.py     # POST /api/detect, analyze-advanced, merge, correct
│   └── items.py         # POST /api/items, /{id}/attachments
├── schemas/             # Pydantic request/response models
│   ├── __init__.py      # Schema aggregation
│   ├── auth.py          # LoginRequest, LoginResponse
│   ├── items.py         # ItemInput, BatchCreateRequest
│   └── detection.py     # DetectedItemResponse, MergeItemsRequest, etc.
└── services/            # Service layer for orchestration
    ├── __init__.py      # Service aggregation
    ├── ai_service.py    # OpenAI vision operations
    └── homebox_service.py  # Homebox API operations
```

### Router Pattern

Each router is a self-contained module with:
- An `APIRouter` instance with a prefix (e.g., `/api`)
- Endpoint handlers that use FastAPI dependencies
- Clear input/output types via Pydantic schemas

### Dependencies (`dependencies.py`)

Shared dependencies provide:
- `get_client()` → Returns `AsyncHomeboxClient` singleton
- `get_token()` → Extracts and validates bearer token from `Authorization` header
- `get_labels_for_context()` → Fetches labels for AI context
- `require_openai_key()` → Validates OpenAI API key is configured

### Service Layer

Services encapsulate external API logic:
- `AIService` → OpenAI operations (detect, analyze, merge, correct)
- `HomeboxService` → Homebox API operations (login, locations, labels, items)

This allows mocking for tests and isolates third-party dependencies.

---

## Frontend Architecture

The frontend is a React + TypeScript SPA with Vite and Tailwind:

### Directory Structure

```
frontend/
├── package.json         # Dependencies and scripts
├── tsconfig.json        # TypeScript config
├── vite.config.ts       # Vite config (proxy, build output)
├── tailwind.config.js   # Tailwind theme config
└── src/
    ├── main.tsx         # React entry point
    ├── App.tsx          # Root component, wizard routing
    ├── api/
    │   ├── client.ts    # Fetch wrapper with retry/backoff
    │   └── types.ts     # TypeScript interfaces (mirrors Pydantic)
    ├── store/
    │   └── index.ts     # Zustand store for wizard state
    ├── components/
    │   ├── ui/          # Reusable: Button, Input, Toast, Loader, StepIndicator
    │   ├── layout/      # AppShell, Header, OfflineBanner, VersionFooter
    │   └── features/    # Login, LocationPicker, ImageCapture, ItemReview, Summary
    ├── hooks/
    │   ├── useToast.ts  # Global toast notifications
    │   └── useOnlineStatus.ts  # Network status tracking
    └── styles/
        └── globals.css  # Tailwind imports, CSS variables
```

### State Management (Zustand)

The store manages the entire wizard flow:
- **Auth slice**: token, isAuthenticated
- **Location slice**: locations, selectedLocation
- **Capture slice**: capturedImages, currentStep
- **Review slice**: detectedItems, reviewedItems, currentItemIndex
- **UI slice**: isLoading, isOnline, toasts

### API Client

The API client (`src/api/client.ts`) provides:
- Automatic retry with exponential backoff
- Configurable timeout
- Typed wrappers for all backend endpoints
- Consistent error handling via `ApiRequestError`

### Component Organization

- **UI components**: Atomic, reusable (no business logic)
- **Layout components**: App shell, navigation, toasts
- **Feature components**: Business logic for each wizard step

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

## Core Library (`homebox_vision/`)

The `homebox_vision` package provides reusable components:

```
homebox_vision/
├── __init__.py   # Public exports
├── client.py     # HomeboxClient (sync) & AsyncHomeboxClient
├── config.py     # Settings from environment variables
├── llm.py        # OpenAI vision: detect, analyze, merge, correct
└── models.py     # DetectedItem dataclass
```

### Key Exports

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
    discriminatory_detect_items,
    
    # Image encoding
    encode_image_to_data_uri,
    encode_image_bytes_to_data_uri,
)
```

---

## Running the Application

### Backend

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

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server (proxies /api to localhost:8000)
npm run dev

# Build for production (outputs to server/static/)
npm run build
```

Then open `http://localhost:8000` (backend serves static) or `http://localhost:5173` (Vite dev server).

---

## Version Management

Keep versions synchronized across:
- `pyproject.toml` - The source of truth
- `server/main.py` - FastAPI app version (for API docs)
- `homebox_vision/__init__.py` - Package `__version__`
- `frontend/package.json` - Frontend package version

Increment all locations when releasing a new version.

### Cache-Busting (Legacy Frontend)

The legacy frontend in `server/static/` uses query parameters for cache-busting:

```html
<link rel="stylesheet" href="/static/styles.css?v=X.Y.Z">
<script src="/static/app.js?v=X.Y.Z"></script>
```

When updating the legacy frontend, update these query parameters.

---

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_client.py

# Run integration tests (requires API keys)
uv run pytest -m integration

# Run with coverage
uv run pytest --cov=homebox_vision
```

---

## Future Multi-App Support

The architecture is designed to support multiple companion apps via a hamburger menu. When adding new apps:

1. Add a new feature directory under `frontend/src/components/features/`
2. Add new wizard steps to the Zustand store
3. Add corresponding backend routers under `server/routers/`
4. The layout/navigation can be extended for app switching
5. Keep shared UI components in `components/ui/`

The modular structure ensures each companion app is isolated while sharing common infrastructure.

---

## API Endpoints Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/login` | No | Authenticate with Homebox |
| GET | `/api/locations` | Yes | List all locations (flat) |
| GET | `/api/locations/tree` | Yes | Get hierarchical location tree |
| GET | `/api/locations/{id}` | Yes | Get single location details |
| GET | `/api/labels` | Yes | List all labels |
| POST | `/api/detect` | No* | Detect items in uploaded image |
| POST | `/api/analyze-advanced` | No* | Multi-image item analysis |
| POST | `/api/merge-items` | No* | Merge items using AI |
| POST | `/api/correct-item` | No* | Correct item with feedback |
| POST | `/api/items` | Yes | Batch create items in Homebox |
| POST | `/api/items/{id}/attachments` | Yes | Upload item attachment |
| GET | `/api/version` | No | Get API version info |

*Detection endpoints require OpenAI API key to be configured on server
