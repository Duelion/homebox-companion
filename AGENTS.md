# Agent Guidelines

Instructions for AI/LLM agents working on this codebase.

---

## Environment & Tooling

- Target any Homebox instance via the `HBC_HOMEBOX_URL` environment variable (we automatically append `/api/v1`). For testing, use the **demo** server at `https://demo.homebox.software` with demo credentials (`demo@example.com` / `demo`).
- Manage Python tooling with **uv**: create a virtual environment via `uv venv`, add dependencies with `uv add`, and run scripts with `uv run`. Keep dependencies tracked in `pyproject.toml` and `uv.lock`.
- The OpenAI API key is provided via the `HBC_OPENAI_API_KEY` environment variable.
- When testing functionality, hit the real demo API and the real OpenAI API rather than mocks or stubs.
- Run `uv run ruff check .` before sending a commit to keep lint feedback consistent.
- Increment the project version number in `pyproject.toml` for every pull request.
- **Frontend dependencies**: When modifying `frontend/package.json`, always run `npm install` in the `frontend/` directory to update `package-lock.json`, then commit both files together. The CI uses `npm ci` which requires the lock file to be in sync.

---

## Environment Variables

All environment variables use the `HBC_` prefix (short for Homebox Companion):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HBC_OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `HBC_HOMEBOX_URL` | No | Demo server | Your Homebox instance URL (we append `/api/v1`) |
| `HBC_OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model for vision |
| `HBC_SERVER_HOST` | No | `0.0.0.0` | Server bind address |
| `HBC_SERVER_PORT` | No | `8000` | Server port (serves both API and frontend in production) |
| `HBC_LOG_LEVEL` | No | `INFO` | Logging level |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Svelte Frontend                              │
│  (SvelteKit + Tailwind CSS - runs in browser)                   │
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
│  (Python - server/app.py)                                       │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/login              → Proxy to Homebox login          │
│  GET  /api/locations          → Fetch locations (flat list)     │
│  GET  /api/locations/tree     → Fetch locations (hierarchical)  │
│  GET  /api/locations/{id}     → Fetch single location details   │
│  GET  /api/labels             → Fetch labels (auth required)    │
│  POST /api/items              → Batch create items in Homebox   │
│  POST /api/items/{id}/attach  → Upload item attachment          │
│  POST /api/tools/vision/detect    → Upload image, run detection │
│  POST /api/tools/vision/analyze   → Multi-image analysis        │
│  POST /api/tools/vision/merge     → Merge multiple items        │
│  POST /api/tools/vision/correct   → Correct item with feedback  │
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
homebox-companion/
├── src/
│   └── homebox_companion/          # Python package
│       ├── __init__.py             # Public API exports
│       ├── core/                   # Core infrastructure
│       │   ├── config.py           # Settings (HBC_* env vars)
│       │   ├── exceptions.py       # Custom exceptions
│       │   └── logging.py          # Loguru setup
│       ├── homebox/                # Homebox API client
│       │   ├── client.py           # Async client only
│       │   └── models.py           # Location, Item, Label
│       ├── ai/                     # AI/LLM abstraction
│       │   ├── images.py           # Image encoding utilities
│       │   ├── openai.py           # OpenAI client wrapper
│       │   └── prompts.py          # Shared prompt templates
│       └── tools/                  # Tool modules (expandable)
│           ├── base.py             # BaseTool abstract class
│           └── vision/             # Vision tool
│               ├── detector.py     # detect_items_from_bytes
│               ├── analyzer.py     # analyze_item_details
│               ├── merger.py       # merge_items_with_openai
│               ├── corrector.py    # correct_item_with_openai
│               ├── models.py       # DetectedItem
│               └── prompts.py      # Vision-specific prompts
│
├── server/                         # FastAPI web app
│   ├── app.py                      # App factory + lifespan
│   ├── dependencies.py             # DI: get_client, get_token
│   ├── api/                        # API routers
│   │   ├── __init__.py             # Router aggregation
│   │   ├── auth.py                 # /api/login
│   │   ├── locations.py            # /api/locations/*
│   │   ├── labels.py               # /api/labels
│   │   ├── items.py                # /api/items/*
│   │   └── tools/
│   │       └── vision.py           # /api/tools/vision/*
│   └── schemas/                    # Pydantic models
│       ├── auth.py
│       ├── items.py
│       └── vision.py
│
├── frontend/                       # Svelte frontend
│   ├── package.json
│   ├── svelte.config.js
│   ├── tailwind.config.js
│   ├── vite.config.ts
│   └── src/
│       ├── app.html                # HTML shell
│       ├── app.css                 # Tailwind imports
│       ├── lib/
│       │   ├── api.ts              # API client
│       │   ├── stores/             # Svelte stores
│       │   │   ├── auth.ts
│       │   │   ├── locations.ts
│       │   │   ├── items.ts
│       │   │   └── ui.ts
│       │   └── components/         # Reusable components
│       └── routes/                 # SvelteKit pages
│           ├── +layout.svelte
│           ├── +page.svelte        # Login
│           ├── location/
│           ├── capture/
│           ├── review/
│           ├── summary/
│           └── success/
│
├── tests/                          # Test suite
├── pyproject.toml                  # Python project config
├── uv.lock                         # Dependency lock
├── AGENTS.md                       # This file
└── README.md                       # User documentation
```

---

## Running the Application

### Backend (Python)

```bash
# Install dependencies
uv sync

# Set required environment variables
export HBC_OPENAI_API_KEY="sk-your-key"
export HBC_HOMEBOX_URL="https://your-homebox.example.com"

# Start the server
uv run python -m server.app

# Or with uvicorn directly (with hot reload)
uv run uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Svelte)

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies API to localhost:8000)
npm run dev

# Build for production
npm run build
```

For production, build the frontend and serve static files from the backend:
```bash
cd frontend && npm run build
# Copy build output to server/static/ (or configure backend to serve from frontend/build)
```

---

## Adding New Tools

To add a new AI-powered tool (e.g., location description generator):

1. **Create tool module**: `src/homebox_companion/tools/location_describer/`
   - `__init__.py` - exports
   - `describer.py` - main logic
   - `prompts.py` - tool-specific prompts

2. **Add API router**: `server/api/tools/location_describer.py`
   - Define endpoints
   - Register in `server/api/tools/__init__.py`

3. **Add frontend page/component** (if needed)

4. **Inherit from `BaseTool`** for consistent interface:
   ```python
   from homebox_companion.tools.base import BaseTool

   class LocationDescriber(BaseTool):
       @property
       def name(self) -> str:
           return "location_describer"

       @property
       def description(self) -> str:
           return "Generate descriptions for locations"

       async def execute(self, *args, **kwargs):
           # Implementation
           pass
   ```

---

## Key Library Exports

```python
from homebox_companion import (
    # Configuration
    settings,
    
    # Client (async only)
    HomeboxClient,
    
    # Exceptions
    AuthenticationError,
    
    # Data models
    DetectedItem,
    
    # Detection functions (all async)
    detect_items_from_bytes,
    discriminatory_detect_items,
    
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

Version is defined in a single place: `pyproject.toml`

The package reads it at runtime using `importlib.metadata`:
```python
from importlib.metadata import version
__version__ = version("homebox-companion")
```

Increment version in `pyproject.toml` only.

---

## Deployment

The application deploys to a homelab server via GitHub Actions on push to `main`.

### Pre-Commit Checklist

Before pushing changes, ensure:

1. **Python changes**: Run `uv run ruff check .` to verify linting
2. **Frontend dependency changes**: If you modified `frontend/package.json`:
   ```bash
   cd frontend
   npm install
   ```
   Then commit both `package.json` and `package-lock.json` together.
3. **Version bump**: Increment version in `pyproject.toml` for PRs

### How Deployment Works

The frontend uses `@sveltejs/adapter-static` to build as a static SPA. The FastAPI backend serves these static files from `server/static/`.

**GitHub Actions workflow** (`.github/workflows/deploy.yml`):

```yaml
name: Deploy to homelab

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - name: Deploy latest code and restart service
        run: |
          set -e
          cd /home/homebox/homebox-app
          
          # Pull latest main
          git fetch origin
          git reset --hard origin/main
          
          # Update Python dependencies
          uv sync
          
          # Build frontend
          cd frontend
          npm ci
          npm run build
          
          # Copy built frontend to server/static
          rm -rf ../server/static/*
          cp -r build/* ../server/static/
          cd ..
          
          # Restart the app
          sudo systemctl restart homebox-vision.service
```

### Common Deployment Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `npm ci` fails with "Missing package from lock file" | `package-lock.json` out of sync | Run `npm install` locally and commit the updated lock file |
| Frontend not updating | Build output not copied | Check `server/static/` contains the build files |
| 404 on frontend routes | SPA fallback not working | Ensure `+layout.ts` has `export const ssr = false` |
