# Agent Guidelines

## Environment & Tooling
- Target the Homebox **demo** API at `https://demo.homebox.software/api/v1` using the demo credentials (`demo@example.com` / `demo`). Do not reference or use production environments.
- Manage Python tooling with **uv**: create a virtual environment via `uv venv`, add dependencies with `uv add`, and run scripts with `uv run`. Keep dependencies tracked in `pyproject.toml` and `uv.lock`.
- The OpenAI API key is provided via the `OPENAI_API_KEY` environment variable.
- When testing functionality, hit the real demo API and the real OpenAI API rather than mocks or stubs.
- Run `uv run ruff check .` before sending a commit to keep lint feedback consistent.
- Increment the project version number in `pyproject.toml` for every pull request.

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
┌─────────────────────────┐     ┌─────────────────────────┐
│   Homebox Demo API      │     │     OpenAI API          │
│   (External)            │     │     (Vision/LLM)        │
└─────────────────────────┘     └─────────────────────────┘
```

---

## Running the Application

```bash
# Install dependencies
uv sync

# Start the server (default port 8000)
uv run python -m server.main

# Or with uvicorn directly
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in a mobile browser or desktop browser with mobile emulation.
