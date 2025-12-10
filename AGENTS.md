# Agent Guidelines

Instructions for AI/LLM agents working on this codebase.

> **For user documentation** (installation, Docker deployment, features): See [README.md](README.md)

---

## Overview

**Homebox Companion** is an AI-powered companion app for [Homebox](https://github.com/sysadminsmedia/homebox) inventory management. Users take photos of items, and OpenAI GPT-5 vision automatically identifies and catalogs them.

---

## Development Setup

### Environment & Tooling

- **Python**: Use `uv` for package management (`uv sync`, `uv add`, `uv run`)
- **Frontend**: Use `npm` in the `frontend/` directory
- **Linting**: Run `uv run ruff check .` before commits
- **Testing**: Use real APIs (demo Homebox + OpenAI), not mocks

### Required Environment Variables

```bash
HBC_OPENAI_API_KEY=sk-your-key          # Required
HBC_HOMEBOX_URL=https://demo.homebox.software  # Optional, defaults to demo
```

Demo credentials: `demo@example.com` / `demo`

### OpenAI Model Policy

**Use GPT-5 models only**: `gpt-5-mini` (default) or `gpt-5-nano` (faster/cheaper).

Do NOT use or reference GPT-4 models (gpt-4o, gpt-4o-mini, etc.) - they are deprecated for this project.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Svelte Frontend                              │
│  (SvelteKit + Tailwind CSS + Svelte 5 runes)                    │
├─────────────────────────────────────────────────────────────────┤
│  • ScanWorkflow class manages entire scan-to-submit flow        │
│  • Thin view pattern: pages delegate to workflow                │
│  • Components: QrScanner, LocationModal, ThumbnailEditor, etc.  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  (Python - server/app.py)                                       │
├─────────────────────────────────────────────────────────────────┤
│  /api/login, /api/locations/*, /api/labels, /api/items/*        │
│  /api/tools/vision/* (detect, analyze, merge, correct)          │
│  /api/settings/* (field-preferences, prompt-preview)            │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────────┐     ┌─────────────────────────────┐
│   Homebox Instance          │     │     OpenAI API              │
│   (Self-hosted or demo)     │     │     (GPT-5 Vision)          │
└─────────────────────────────┘     └─────────────────────────────┘
```

---

## Project Structure

```
homebox-companion/
├── src/homebox_companion/           # Python package
│   ├── __init__.py                  # Public API exports
│   ├── core/
│   │   ├── config.py                # Settings (HBC_* env vars)
│   │   ├── field_preferences.py     # AI customization storage
│   │   ├── exceptions.py            # Custom exceptions
│   │   └── logging.py               # Loguru setup
│   ├── homebox/
│   │   ├── client.py                # Async HTTP client
│   │   └── models.py                # Location, Item, Label
│   ├── ai/
│   │   ├── images.py                # Image encoding utilities
│   │   ├── openai.py                # OpenAI client wrapper
│   │   ├── prompts.py               # Shared prompt templates
│   │   └── vision_prompts.py        # Vision-specific prompts
│   └── tools/vision/
│       ├── detector.py              # detect_items_from_bytes
│       ├── analyzer.py              # analyze_item_details
│       ├── merger.py                # merge_items_with_openai
│       ├── corrector.py             # correct_item_with_openai
│       ├── models.py                # DetectedItem dataclass
│       └── prompts.py               # Detection prompts
│
├── server/                          # FastAPI backend
│   ├── app.py                       # App factory + lifespan
│   ├── dependencies.py              # DI: get_client, get_token, VisionContext
│   ├── api/
│   │   ├── auth.py                  # /api/login
│   │   ├── locations.py             # /api/locations/*
│   │   ├── labels.py                # /api/labels
│   │   ├── items.py                 # /api/items/*
│   │   ├── field_preferences.py     # /api/settings/*
│   │   └── tools/vision.py          # /api/tools/vision/*
│   └── schemas/                     # Pydantic request/response models
│
├── frontend/                        # Svelte frontend
│   └── src/
│       ├── lib/
│       │   ├── api/                 # Split API modules
│       │   │   ├── client.ts        # Base fetch wrapper
│       │   │   ├── auth.ts, locations.ts, labels.ts, items.ts
│       │   │   ├── vision.ts        # AI detection endpoints
│       │   │   └── settings.ts      # Field preferences
│       │   ├── types/index.ts       # Consolidated TypeScript types
│       │   ├── workflows/
│       │   │   └── scan.svelte.ts   # ScanWorkflow class (Svelte 5)
│       │   ├── stores/              # Svelte stores
│       │   │   ├── auth.ts, locations.ts, labels.ts, ui.ts
│       │   └── components/          # Reusable components
│       │       ├── QrScanner.svelte
│       │       ├── LocationModal.svelte
│       │       ├── ThumbnailEditor.svelte
│       │       └── ...
│       └── routes/                  # SvelteKit pages
│           ├── +page.svelte         # Login
│           ├── location/            # Location selection
│           ├── capture/             # Photo capture
│           ├── review/              # Item review
│           ├── summary/             # Submission summary
│           ├── success/             # Success page
│           └── settings/            # Settings page
│
├── tests/                           # Test suite
├── pyproject.toml                   # Python config + version
└── Dockerfile                       # Multi-stage Docker build
```

---

## Frontend Architecture

### ScanWorkflow Pattern (Svelte 5)

The frontend uses a class-based workflow pattern with Svelte 5 runes:

```typescript
// lib/workflows/scan.svelte.ts
class ScanWorkflow {
    state = $state<ScanState>({...});  // Reactive state
    
    // Actions
    setLocation(id, name, path) {...}
    addImage(file, options) {...}
    async startAnalysis() {...}
    confirmCurrentItem() {...}
    async submitConfirmedItems() {...}
}

export const scanWorkflow = new ScanWorkflow();
```

**Key concepts:**
- Single source of truth for the entire scan flow
- State persists across tab navigation
- Pages are "thin views" that render workflow state
- Analysis continues in background even when navigating away

### API Client Structure

```typescript
// lib/api/client.ts - Base request wrapper with auth handling
// lib/api/vision.ts - AI detection endpoints
// lib/api/settings.ts - Field preferences + prompt preview
```

### Component Patterns

- Use Svelte 5 `$props()` for component inputs
- Use `$state()` for local reactive state
- Emit events via callback props (e.g., `onScan`, `onClose`)

---

## Backend Patterns

### VisionContext Dependency

Shared context for vision endpoints:

```python
@dataclass
class VisionContext:
    token: str
    labels: list[dict]
    field_preferences: FieldPreferences
    output_language: str | None
    default_label_id: str | None

async def get_vision_context(...) -> VisionContext:
    # Loads labels, preferences in one place
```

### Field Preferences

AI customization is stored in `config/field_preferences.json` with env var fallbacks:

```python
def load_field_preferences() -> FieldPreferences:
    # 1. Load env var defaults (HBC_AI_*)
    # 2. Overlay with file-based preferences (UI settings win)
```

---

## AI Tool Development

### Prompt Architecture

Prompts are built modularly in `src/homebox_companion/ai/prompts.py`:

```python
FIELD_DEFAULTS = {
    "name": "Title Case, no quantity, max 255 characters",
    "description": "max 1000 chars, condition/attributes only",
    # ...
}

def build_naming_rules(customizations) -> str: ...
def build_item_schema(customizations) -> str: ...
def build_extended_fields_schema(customizations) -> str: ...
def build_label_prompt(labels) -> str: ...
```

User customizations **replace** defaults (not append).

### Adding New AI Tools

1. Create module: `src/homebox_companion/tools/new_tool/`
2. Add API router: `server/api/tools/new_tool.py`
3. Register in `server/api/__init__.py`
4. Add frontend integration as needed

### Extended Fields

These fields require a PUT after item creation (Homebox API limitation):

| Field | Description |
|-------|-------------|
| `manufacturer` | Brand name |
| `model_number` | Model/part number |
| `serial_number` | Serial number |
| `purchase_price` | Price (number only) |
| `purchase_from` | Retailer name |
| `notes` | Condition/defects only |

---

## Testing

```bash
# Unit tests
uv run pytest

# Integration tests (requires HBC_OPENAI_API_KEY)
uv run pytest -m integration
```

Integration tests hit the real Homebox demo server and OpenAI API.

---

## Pre-Commit Checklist

1. **Lint**: `uv run ruff check .`
2. **Frontend types**: `cd frontend && npm run check` (runs svelte-check for TypeScript errors)
3. **Frontend deps**: If `package.json` changed, run `npm install` and commit both files
4. **Version**: Increment in `pyproject.toml` for releases

---

## Version Management

Version is defined in `pyproject.toml` only. Read at runtime:

```python
from importlib.metadata import version
__version__ = version("homebox-companion")
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` | Authenticate with Homebox |
| GET | `/api/locations` | List all locations |
| GET | `/api/locations/tree` | Get hierarchical location tree |
| GET | `/api/locations/{id}` | Get single location with children |
| POST | `/api/locations` | Create a new location |
| PUT | `/api/locations/{id}` | Update a location |
| GET | `/api/labels` | List all labels |
| POST | `/api/items` | Batch create items |
| POST | `/api/items/{id}/attachments` | Upload item attachment |
| POST | `/api/tools/vision/detect` | Detect items in a single image |
| POST | `/api/tools/vision/detect-batch` | Detect items in multiple images |
| POST | `/api/tools/vision/analyze` | Multi-image analysis |
| POST | `/api/tools/vision/merge` | Merge multiple items using AI |
| POST | `/api/tools/vision/correct` | Correct item with user feedback |
| GET | `/api/settings/field-preferences` | Get AI customization settings |
| PUT | `/api/settings/field-preferences` | Update AI customization settings |
| POST | `/api/settings/prompt-preview` | Preview AI prompt with current settings |
| GET | `/api/version` | Get application version |

---

## Library Usage

The `homebox_companion` package can be used as a Python library:

```python
import asyncio
from homebox_companion import detect_items_from_bytes, HomeboxClient, ItemCreate

async def main():
    # Detect items in an image
    with open("items.jpg", "rb") as f:
        items = await detect_items_from_bytes(f.read())
    
    for item in items:
        print(f"{item.name}: {item.quantity}")

    # Create items in Homebox
    async with HomeboxClient() as client:
        token = await client.login("user@example.com", "password")
        locations = await client.list_locations(token)
        
        for item in items:
            created = await client.create_item(token, ItemCreate(
                name=item.name,
                quantity=item.quantity,
                description=item.description,
                location_id=locations[0]["id"],
            ))
            print(f"Created: {created['name']}")

asyncio.run(main())
```

### Key Exports

```python
from homebox_companion import (
    # Config
    settings, Settings,
    
    # Client
    HomeboxClient, ItemCreate, ItemUpdate,
    
    # Exceptions
    AuthenticationError,
    
    # Vision
    DetectedItem, detect_items_from_bytes, discriminatory_detect_items,
    analyze_item_details_from_images, correct_item_with_openai, merge_items_with_openai,
    
    # Utilities
    encode_image_to_data_uri, encode_image_bytes_to_data_uri,
)
```
