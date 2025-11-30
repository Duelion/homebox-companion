# homebox

Utilities for interacting with the Homebox demo API.

The package exposes a small, pythonic API that pairs the Homebox demo environment with
OpenAI vision helpers so the community can build quick experiments without reimplementing
HTTP plumbing or prompt scaffolding.

## Setup (uv)

1. Create and activate a virtual environment managed by **uv**:

   ```bash
   uv venv
   source .venv/bin/activate
   ```

2. Install dependencies from `pyproject.toml` / `uv.lock`:

   ```bash
   uv sync
   ```

3. To add new dependencies, prefer `uv add <package>` so both `pyproject.toml` and `uv.lock` stay in sync.

## Linting

Run Ruff with uv to keep contributions consistent:

```bash
uv run ruff .
```

## Create an item via the demo API

Run the helper script with uv. It logs into the demo instance using the demo credentials (`demo@example.com` / `demo`), picks the first available location, and creates a uniquely named item.

```bash
uv run python create_homebox_item.py
```

## Library usage

The `homebox` package targets the demo environment
(`https://demo.homebox.software/api/v1`) using the provided demo credentials. It exposes
helpers for both raw API access and OpenAI-powered image parsing.

### Create items with the demo client

```bash
uv run python - <<'PY'
from datetime import UTC, datetime

from homebox import DetectedItem, HomeboxDemoClient

client = HomeboxDemoClient()
token = client.login()  # uses demo@example.com / demo
location_id = client.list_locations(token)[0]["id"]

item = DetectedItem(
    name=f"Demo API item {datetime.now(UTC).isoformat(timespec='seconds')}",
    quantity=1,
    description="Created via automation script.",
    location_id=location_id,
)

created = client.create_items(token, [item])
print(created)
PY
```

### Detect items with OpenAI vision

Example usage (requires `OPENAI_API_KEY`):

```bash
uv run python - <<'PY'
from pathlib import Path

from homebox import HomeboxDemoClient, detect_items_with_openai

image_path = Path("/path/to/photo.jpg")
items = detect_items_with_openai(image_path, api_key="${OPENAI_API_KEY}")

client = HomeboxDemoClient()
token = client.login()  # uses demo@example.com / demo
created = client.create_items(token, items)
print(created)
PY
```

The `detect_items_with_openai` helper prompts the OpenAI API to return Homebox-ready entries
with `name` (<=255 characters), integer `quantity`, and an optional `description` (<=1000
characters) summarizing the item. The client enforces these limits before posting each item
to the demo API's `/items` endpoint.
