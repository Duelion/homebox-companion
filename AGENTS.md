# Agent Guidelines

Instructions for AI/LLM agents working on this codebase.

> **For user documentation** (installation, Docker deployment, features): See [README.md](README.md)

---

## Overview

**Homebox Companion** is an AI-powered companion app for [Homebox](https://github.com/sysadminsmedia/homebox) inventory management. Users take photos of items, and AI vision models automatically identify and catalog them.

---

## Development Setup

### Environment & Tooling

- **Python**: Use `uv` for package management (`uv sync`, `uv add`, `uv run`)
- **Frontend**: Use `npm` in the `frontend/` directory
- **Linting**: Run `uv run ruff check .` before commits
- **Testing**: Use real APIs (demo Homebox + LLM provider), not mocks

### Required Environment Variables

```bash
HBC_LLM_API_KEY=sk-your-key             # Required (replaces HBC_OPENAI_API_KEY)
HBC_LLM_MODEL=gpt-5-mini                # Optional, defaults to gpt-5-mini
HBC_LLM_API_BASE=https://...            # Optional, for OpenRouter/proxies
HBC_HOMEBOX_URL=https://demo.homebox.software  # Optional, defaults to demo
```

Legacy variables (`HBC_OPENAI_API_KEY`, `HBC_OPENAI_MODEL`) still work but are deprecated.

Demo credentials: `demo@example.com` / `demo`

### LLM Provider Policy

**This app uses LiteLLM** for multi-provider support. Any vision-capable model is supported:
- OpenAI: `gpt-5-mini` (default), `gpt-5-nano`, `gpt-4o`, `gpt-4o-mini`
- Anthropic: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`
- Google: `gemini-2.0-flash`, `gemini-1.5-pro`
- OpenRouter: `openrouter/provider/model` (requires `HBC_LLM_API_BASE`)

Model names are passed directly to LiteLLM - do not modify or extract base names.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Svelte Frontend                              │
│  (SvelteKit + Tailwind CSS + Svelte 5 runes)                    │
├─────────────────────────────────────────────────────────────────┤
│  • ScanWorkflow coordinates specialized services                 │
│  • Services: Capture, Analysis, Review, Submission               │
│  • Thin view pattern: pages delegate to workflow                 │
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
│  /api/settings/* (field-preferences, effective-defaults)        │
│  /api/config, /api/logs, /api/version                           │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────────┐     ┌─────────────────────────────┐
│   Homebox Instance          │     │   LLM Provider API          │
│   (Self-hosted or demo)     │     │   (Vision-capable models)   │
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
│   │   └── models.py                # Location, Item, Label, ItemCreate, ItemUpdate
│   ├── ai/
│   │   ├── images.py                # Image encoding utilities
│   │   ├── llm.py                   # LiteLLM client wrapper (multi-provider)
│   │   ├── model_capabilities.py    # Runtime capability checking via LiteLLM
│   │   └── prompts.py               # Shared prompt templates
│   └── tools/vision/
│       ├── detector.py              # detect_items_from_bytes
│       ├── analyzer.py              # analyze_item_details
│       ├── merger.py                # merge_items (LLM-based)
│       ├── corrector.py             # correct_item (LLM-based)
│       ├── models.py                # DetectedItem dataclass
│       └── prompts.py               # Detection prompts
│
├── server/                          # FastAPI backend
│   ├── app.py                       # App factory + lifespan + version check
│   ├── dependencies.py              # DI: get_client, get_token, VisionContext
│   ├── api/
│   │   ├── __init__.py              # Router aggregation
│   │   ├── auth.py                  # /api/login
│   │   ├── config.py                # /api/config (non-sensitive config)
│   │   ├── locations.py             # /api/locations/*
│   │   ├── labels.py                # /api/labels
│   │   ├── items.py                 # /api/items/* (CRUD + attachments)
│   │   ├── logs.py                  # /api/logs (view + download)
│   │   ├── field_preferences.py     # /api/settings/*
│   │   └── tools/vision.py          # /api/tools/vision/*
│   └── schemas/                     # Pydantic request/response models
│       ├── auth.py, items.py, locations.py, vision.py
│
├── frontend/                        # Svelte frontend
│   └── src/
│       ├── lib/
│       │   ├── api/                 # Split API modules
│       │   │   ├── client.ts        # Base fetch wrapper + ApiError
│       │   │   ├── auth.ts          # Login
│       │   │   ├── locations.ts     # Location CRUD
│       │   │   ├── labels.ts        # Labels list
│       │   │   ├── items.ts         # Item creation + attachments
│       │   │   ├── vision.ts        # AI detection endpoints
│       │   │   ├── settings.ts      # Config, logs, field preferences
│       │   │   └── index.ts         # Re-exports all APIs
│       │   ├── types/index.ts       # Consolidated TypeScript types
│       │   ├── workflows/           # State management (Svelte 5 runes)
│       │   │   ├── scan.svelte.ts   # ScanWorkflow coordinator
│       │   │   ├── capture.svelte.ts    # CaptureService
│       │   │   ├── analysis.svelte.ts   # AnalysisService
│       │   │   ├── review.svelte.ts     # ReviewService
│       │   │   ├── submission.svelte.ts # SubmissionService
│       │   │   └── index.ts         # Exports
│       │   ├── stores/              # Svelte stores
│       │   │   ├── auth.ts          # Token + session expiry
│       │   │   ├── locations.ts     # Location tree cache
│       │   │   ├── labels.ts        # Labels cache
│       │   │   └── ui.ts            # App version + UI state
│       │   ├── components/          # Reusable components
│       │   │   ├── QrScanner.svelte
│       │   │   ├── LocationModal.svelte
│       │   │   ├── ThumbnailEditor.svelte
│       │   │   ├── ItemPickerModal.svelte   # Parent item selection
│       │   │   ├── SessionExpiredModal.svelte
│       │   │   ├── AiCorrectionPanel.svelte
│       │   │   ├── ExtendedFieldsPanel.svelte
│       │   │   └── ... (18 total)
│       │   └── utils/               # Utility functions
│       │       ├── imageCompression.ts
│       │       ├── logger.ts        # Domain-specific loggers
│       │       ├── retry.ts         # Retry with exponential backoff
│       │       ├── routeGuard.ts    # Auth route guards
│       │       └── token.ts         # Token validation
│       └── routes/                  # SvelteKit pages
│           ├── +layout.svelte       # Global layout + SessionExpiredModal
│           ├── +page.svelte         # Login
│           ├── location/            # Location selection + parent item
│           ├── capture/             # Photo capture + image options
│           ├── review/              # Item review + AI correction
│           ├── summary/             # Submission summary
│           ├── success/             # Success page
│           └── settings/            # Settings (config, logs, field prefs)
│
├── tests/                           # Test suite
├── config/                          # Runtime config storage
│   └── field_preferences.json       # User AI customizations (persisted)
├── logs/                            # Application logs (daily rotation)
├── pyproject.toml                   # Python config + version
└── Dockerfile                       # Multi-stage Docker build
```

---

## Frontend Architecture

### Workflow Service Decomposition

The scan workflow is decomposed into focused services, each handling one phase:

```typescript
// lib/workflows/scan.svelte.ts - Coordinator
class ScanWorkflow {
    private captureService = new CaptureService();    // Image management
    private analysisService = new AnalysisService();  // AI detection
    private reviewService = new ReviewService();      // Item review/confirmation
    private submissionService = new SubmissionService(); // Homebox submission

    // Unified state accessor via Proxy for backward compatibility
    get state(): ScanState { ... }
    
    // Location management
    setLocation(id, name, path) {...}
    setParentItem(id, name) {...}  // For sub-items
    
    // Delegates to services
    addImage(image) {...}          // → CaptureService
    startAnalysis() {...}          // → AnalysisService
    confirmItem(item) {...}        // → ReviewService
    submitAll() {...}              // → SubmissionService
}

export const scanWorkflow = new ScanWorkflow();
```

**Service responsibilities:**

| Service | State Managed | Key Methods |
|---------|--------------|-------------|
| `CaptureService` | `images`, additional images | `addImage()`, `removeImage()`, `addAdditionalImages()` |
| `AnalysisService` | `progress`, default label | `analyze()`, `cancel()`, `loadDefaultLabel()` |
| `ReviewService` | `detectedItems`, `confirmedItems`, `currentReviewIndex` | `confirmCurrentItem()`, `skipCurrentItem()` |
| `SubmissionService` | `progress`, `itemStatuses`, `lastResult`, `lastErrors` | `submitAll()`, `retryFailed()`, `saveResult()` |

**Key concepts:**
- Single source of truth for the entire scan flow
- State persists across tab navigation
- Pages are "thin views" that render workflow state
- Analysis continues in background even when navigating away
- Supports parent item selection for sub-item relationships

### Session Handling

The app handles session expiry gracefully:

```typescript
// lib/stores/auth.ts
export const sessionExpired = writable(false);
export function markSessionExpired() { sessionExpired.set(true); }

// lib/api/client.ts
function handleUnauthorized(response: Response): boolean {
    if (response.status === 401 && get(token)) {
        markSessionExpired();
        return true;
    }
    return false;
}
```

The `SessionExpiredModal` in `+layout.svelte` shows when any API returns 401.

### API Client Structure

```typescript
// lib/api/client.ts
export class ApiError extends Error { status: number; data: unknown; }
export async function request<T>(endpoint, options): Promise<T>
export async function requestFormData<T>(endpoint, formData, options): Promise<T>
export async function requestBlobUrl(endpoint, signal): Promise<string | null>

// lib/api/index.ts - Re-exports all domain APIs
export { auth, locations, labels, items, vision, fieldPreferences }
export { getVersion, getConfig, getLogs, downloadLogs }
```

### Component Patterns

- Use Svelte 5 `$props()` for component inputs
- Use `$state()` for local reactive state
- Emit events via callback props (e.g., `onScan`, `onClose`)
- Use `$effect()` for side effects (e.g., auto-scroll logs)

---

## Backend Patterns

### VisionContext Dependency

Shared context for vision endpoints:

```python
@dataclass
class VisionContext:
    token: str
    labels: list[dict[str, str]]
    field_preferences: dict[str, str] | None  # Effective customizations
    output_language: str | None
    default_label_id: str | None

async def get_vision_context(...) -> VisionContext:
    # Extracts token, fetches labels, loads preferences in one place
```

### Model Capability Checking

LiteLLM provides runtime capability checking:

```python
from homebox_companion.ai.model_capabilities import get_model_capabilities

caps = get_model_capabilities("gpt-4o")
# Returns: ModelCapabilities(model="gpt-4o", vision=True, multi_image=True, json_mode=True)

caps = get_model_capabilities("openrouter/anthropic/claude-3.5-sonnet")
# LiteLLM handles provider routing automatically
```

Models are validated via `litellm.supports_vision()` and `litellm.supports_response_schema()`. 
Set `HBC_LLM_ALLOW_UNSAFE_MODELS=true` to skip validation for unrecognized models.

### Field Preferences

AI customization has three layers:

1. **Hardcoded defaults** in `FieldPreferencesDefaults` (pydantic-settings)
2. **Environment variables** (HBC_AI_*) override hardcoded defaults
3. **File-based preferences** (`config/field_preferences.json`) override env vars

```python
# Load order: hardcoded → env vars → file
def load_field_preferences() -> FieldPreferences:
    # Returns user file preferences (may be empty)

def get_defaults() -> FieldPreferencesDefaults:
    # Returns env var values or hardcoded fallbacks (all fields have values)
```

The `get_effective_customizations()` method merges user prefs with defaults.

### Item Creation Flow

Items are created in two steps due to Homebox API limitations:

```python
# Step 1: POST with basic fields
item = await client.create_item(token, ItemCreate(...))

# Step 2: PUT with extended fields (manufacturer, model, serial, etc.)
if detected_item.has_extended_fields():
    await client.update_item(token, item_id, extended_payload)
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

def build_critical_constraints(single_item: bool) -> str: ...
def build_naming_rules(customizations) -> str: ...
def build_item_schema(customizations) -> str: ...
def build_extended_fields_schema(customizations) -> str: ...
def build_label_prompt(labels) -> str: ...
def build_language_instruction(output_language) -> str: ...
```

User customizations **replace** defaults (not append).

### Detection prompts

`src/homebox_companion/tools/vision/prompts.py` contains:

```python
def build_detection_system_prompt(
    labels: list[dict[str, str]] | None = None,
    single_item: bool = False,
    extra_instructions: str | None = None,
    extract_extended_fields: bool = True,
    field_preferences: dict[str, str] | None = None,
    output_language: str | None = None,
) -> str: ...
```

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

# Integration tests (requires HBC_LLM_API_KEY or HBC_OPENAI_API_KEY)
uv run pytest -m integration
```

Integration tests hit the real Homebox demo server and LLM provider API.

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

### Core API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` | Authenticate with Homebox |
| GET | `/api/version` | Get app version + update check |
| GET | `/api/config` | Get non-sensitive configuration |
| GET | `/api/logs` | Get recent application logs |
| GET | `/api/logs/download` | Download full log file |

### Locations

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/locations` | List all locations |
| GET | `/api/locations/tree` | Get hierarchical location tree |
| GET | `/api/locations/{id}` | Get single location with children |
| POST | `/api/locations` | Create a new location |
| PUT | `/api/locations/{id}` | Update a location |

### Labels & Items

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/labels` | List all labels |
| GET | `/api/items` | List items (optional: `?location_id=`) |
| POST | `/api/items` | Batch create items |
| POST | `/api/items/{id}/attachments` | Upload item attachment |
| GET | `/api/items/{id}/attachments/{aid}` | Proxy attachment (for thumbnails) |

### Vision Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/tools/vision/detect` | Detect items in a single image |
| POST | `/api/tools/vision/detect-batch` | Detect items in multiple images (parallel) |
| POST | `/api/tools/vision/analyze` | Multi-image analysis for details |
| POST | `/api/tools/vision/merge` | Merge multiple items using AI |
| POST | `/api/tools/vision/correct` | Correct item with user feedback |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings/field-preferences` | Get AI customization settings |
| PUT | `/api/settings/field-preferences` | Update AI customization settings |
| DELETE | `/api/settings/field-preferences` | Reset to defaults |
| GET | `/api/settings/effective-defaults` | Get defaults (env or hardcoded) |
| POST | `/api/settings/prompt-preview` | Preview AI prompt with settings |

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
    analyze_item_details_from_images, correct_item, merge_items,
    
    # Utilities
    encode_image_to_data_uri, encode_image_bytes_to_data_uri,
    cleanup_llm_clients,
)
```

---

## Common Pitfalls

### Frontend

1. **Don't modify `state.confirmedItems` directly** - use workflow methods
2. **AbortController** - always check for abort errors in async operations
3. **Proxy state** - `workflow.state` is a Proxy; accessing unknown properties throws

### Backend

1. **Extended fields require PUT** - Homebox API doesn't accept them on create
2. **VisionContext auto-filters default label** - AI suggestions don't include it
3. **Field preferences file location** - `config/field_preferences.json` (created on first save)

### AI Prompts

1. **Customizations replace defaults** - don't concatenate instructions
2. **Single item mode** - forces quantity=1 and treats everything as one item
3. **Extra instructions** - user hints are appended to the prompt
