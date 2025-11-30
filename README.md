# homebox

Utilities for interacting with the Homebox demo API.

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

## Create an item via the demo API

Run the helper script with uv. It logs into the demo instance using the demo credentials (`demo@example.com` / `demo`), picks the first available location, and creates a uniquely named item.

```bash
uv run python create_homebox_item.py
```

## Demo adaptor with OpenAI vision

The `homebox_demo_adapter.py` module targets the demo environment (`https://demo.homebox.software/api/v1`) using the provided demo credentials. It pairs the Homebox API with OpenAI's vision models to turn an image into structured inventory entries and then creates them in the demo account.

Example usage (requires `OPENAI_API_KEY`):

```bash
uv run python - <<'PY'
from pathlib import Path

from homebox_demo_adapter import HomeboxDemoAdapter, detect_items_with_openai

image_path = Path("/path/to/photo.jpg")
items = detect_items_with_openai(image_path, api_key="${OPENAI_API_KEY}")

client = HomeboxDemoAdapter()
token = client.login()  # uses demo@example.com / demo
created = client.create_items(token, items)
print(created)
PY
```

The `detect_items_with_openai` helper prompts the OpenAI API to return Homebox-ready entries with `name` (<=255 characters), integer `quantity`, and an optional `description` (<=1000 characters) summarizing the item. The adapter enforces these limits before posting each item to the demo API's `/items` endpoint.
