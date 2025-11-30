# Agent Guidelines

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
| `HOMEBOX_VISION_OPENAI_MODEL` | No | `gpt-4.1-mini` | OpenAI model for vision |
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
- Present the locations in a dropdown menu for the user to select.
- Store the selected location and use it for all subsequent item operations in this session.

### 3. Image Upload / Capture & Item Detection
- Prompt user to upload a photo or take one using the phone camera.
- Send that image to the backend API endpoint.
- Use the existing vision/LLM logic to call OpenAI (with the model and API key defined in environment variables) to detect and generate a list of items present in the image.

### 4. Pre-fill Item Forms for User Review
- For each detected item, render a form on the frontend with pre-filled values (as suggested by the LLM).
- Allow the user to review and edit each item (e.g., name, quantity, description, location).
- Provide the ability to accept, edit, or skip any item (e.g., if the LLM mistakenly detected a non-relevant object).
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
│  • Location dropdown                                             │
│  • Camera/file upload                                            │
│  • Item review forms                                             │
│  • Summary & confirmation                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  (Python - server/main.py)                                      │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/login          → Proxy to Homebox login              │
│  GET  /api/locations      → Fetch locations (auth required)     │
│  GET  /api/labels         → Fetch labels (auth required)        │
│  POST /api/detect         → Upload image, run LLM detection     │
│  POST /api/items          → Batch create items in Homebox       │
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
│   └── models.py            # Data models
├── server/                   # FastAPI web app
│   ├── __init__.py
│   ├── main.py              # API routes
│   └── static/              # Frontend files
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── tests/                    # Test suite
│   ├── test_client.py       # Client unit tests
│   ├── test_llm.py          # LLM unit tests
│   └── test_integration.py  # Integration tests
├── pyproject.toml           # Project configuration
├── uv.lock                  # Dependency lock file
└── README.md                # Documentation
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

# Or with uvicorn directly
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in a mobile browser or desktop browser with mobile emulation.
