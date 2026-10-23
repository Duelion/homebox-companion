<h1 align="center" style="margin-top: -10px;"></h1>

<div align="center">
  <a href="#"><img src=".github/assets/images/homebox-companion-icon.png" height="200"/></a>
</div>

<h1 align="center" style="margin-top: -10px;"> Homebox Companion </h1>

> **Not affiliated with the Homebox project.** This is an unofficial third-party companion app.

AI-powered companion for [Homebox](https://github.com/sysadminsmedia/homebox) inventory management.
<table align="center">
  <tr>
    <td><img src=".github/assets/images/01_select_location.png" width="180" alt="Select Location"></td>
    <td><img src=".github/assets/images/02_capture_items.png" width="180" alt="Capture Items"></td>
    <td><img src=".github/assets/images/03_review_items.png" width="180" alt="Review Items"></td>
    <td><img src=".github/assets/images/04_submit.png" width="180" alt="Submit"></td>
  </tr>
</table>

Take a photo of your stuff, and let AI identify and catalog items directly into your Homebox instance. Perfect for quickly inventorying a room, shelf, or collection.
Use the **AI Chat** to manage your inventory, find locations, or update details just by asking.

## 🔄 How It Works

```mermaid
flowchart LR
    A[Connect to Homebox<br/>Configured key or legacy login] --> B[📍 Select<br/>Location]
    B --> C[📸 Capture<br/>Photos]
    C --> D[✏️ Review &<br/>Edit Items]
    D --> E[✅ Submit to<br/>Homebox]
    
    B -.-> B1[/Browse, search,<br/>or scan QR/]
    C -.-> C1[/AI analyzes with<br/>OpenAI GPT-5/]
    D -.-> D1[/Edit names,<br/>quantities, tags/]
    
```

1. **Connect** – Enter directly with a configured Homebox API key, or use your existing Homebox credentials when no key is configured
2. **Select Location** – Browse the location tree, search, or scan a Homebox QR code
3. **Capture Photos** – Take or upload photos of items (supports multiple photos per item)
4. **AI Detection** – AI vision (via LiteLLM*) identifies items, quantities, and metadata
5. **Review & Edit** – Adjust AI suggestions or ask AI to correct mistakes
6. **Submit** – Items are created in your Homebox inventory with photos attached

> *LiteLLM is a Python adaptor library we use to call OpenAI directly, no Local AI model required (unless you want to), just your API key.

## 💰 OpenAI Cost Estimates

| Model | Input/1M | Output/1M | Cost per 100 items | Avg Latency | Notes |
|-------|----------|-----------|---------------------|-------------|-------|
| **GPT-5.6 Luna** | $0.20 | $1.20 | **$0.019** 🏆 | ~3.4s | Cheapest. Requires `reasoning_effort=none` |
| GPT-5.4 Nano | $0.20 | $1.25 | $0.024 | ~1.9s | Fastest. Good budget option |
| GPT-5.4 Mini | $0.75 | $4.50 | $0.076 | ~2.0s | 3× more expensive |

**GPT-5.6 Luna** is the recommended model — cheapest at $0.019/100 items with `reasoning_effort=none`. All three models achieved zero errors and comparable detection on inventory classification tasks.

> **Benchmark methodology:** 100 API calls per model using 3 test images with extended field extraction. Costs include OpenAI automatic prompt caching (54–66% of input tokens cached at $0.02/1M). Real-world costs depend on image complexity and item count per photo.
>
> *Prices as of **2026-09-21**, measured against OpenAI's live API.*

## 📋 Requirements

Before you start, you'll need:

- **An OpenAI API key** – Get one at [platform.openai.com](https://platform.openai.com/api-keys)
- **A Homebox instance** – Your own [Homebox](https://github.com/sysadminsmedia/homebox) server

> **Compatibility:** Docker-based live tests default to Homebox v0.27.0 and also run against v0.26.2. Homebox API keys require v0.26.0 or newer; retaining legacy login does not add support for older inventory APIs.

On Homebox 0.27+, AI Chat can keep an item's parent container while setting a separate physical location, or clear that override to follow the parent chain again. The update tool exposes `location_override_id` and `clear_location_override` for these operations; `location_id` still moves the item directly into a location. Explicit overrides require a recognized Homebox version of 0.27.0 or newer. For the upstream 0.27.0 issue where typed custom fields display blank, see the [separate Homebox display patch](docs/upstream/README.md).

## 🚀 Quick Start

### Docker (Recommended)

```yaml
# docker-compose.yml
services:
  homebox-companion:
    image: ghcr.io/duelion/homebox-companion:latest
    container_name: homebox-companion
    restart: always
    environment:
      - HBC_LLM_API_KEY=sk-your-api-key-here
      - HBC_HOMEBOX_URL=http://your-homebox-ip:7745
      - HBC_HOMEBOX_API_KEY=${HBC_HOMEBOX_API_KEY:-}
    ports:
      - 8000:8000
    volumes:
      - companion-data:/app/data
volumes:
  companion-data:
```

```bash
docker compose up -d
```

Open `http://localhost:8000` in your browser.

> **Tip:** If Homebox runs on the same machine but outside Docker, use `http://host.docker.internal:PORT` as the URL.

If Homebox runs in another Compose service, put both services on the same Docker
network and use the Homebox service name, for example `http://homebox:7745`.
`localhost` from inside the Companion container refers to the Companion
container itself.

> **ARM64/Raspberry Pi:** Docker images are built for both `linux/amd64` and `linux/arm64` architectures.

### Persistent Docker settings

Mount `/app/data` to retain settings across container replacement. Fresh named
volumes inherit the image directory's ownership and work with the non-root
`appuser`. Startup checks creation, atomic replacement and removal in both settings
directories before serving requests. Existing volumes and host bind mounts retain
their existing permissions; the image cannot override host filesystem permissions.

If startup reports unwritable storage, stop Companion and back up the selected
mount first. Obtain the actual UID and GID from the exact image you deploy:

```bash
docker run --rm --entrypoint id ghcr.io/duelion/homebox-companion:latest -u
docker run --rm --entrypoint id ghcr.io/duelion/homebox-companion:latest -g
```

For an existing named volume, replace `YOUR_COMPANION_VOLUME` and `UID:GID` below
with the explicitly verified volume name and numeric identity from those commands.
This one-time administrative operation changes only the data directory and its
settings file, preserving contents; the application continues to run non-root:

```bash
docker run --rm --user 0:0 --entrypoint sh \
  -v YOUR_COMPANION_VOLUME:/repair \
  ghcr.io/duelion/homebox-companion:latest \
  -c 'chown UID:GID /repair && if [ -f /repair/settings.yaml ]; then chown UID:GID /repair/settings.yaml; fi'
```

For a Linux host bind mount, verify the absolute host directory and use
`sudo chown UID:GID /absolute/companion-data` and, if present,
`sudo chown UID:GID /absolute/companion-data/settings.yaml`. Ensure the owner has
write and directory traversal permissions. For Docker Desktop bind mounts, grant
the runtime account access using the host filesystem's sharing/ACL controls.
Read-only mounts must be made writable. Do not delete settings, recursively change
ownership of unrelated directories, or grant world-write permissions as a repair.
Restart Companion after correcting the selected mount.

### Saved field preferences

Field preferences keep their existing JSON format and
`/app/config/field_preferences.json` path. In the Docker image, this file points
to `/app/data/config/field_preferences.json`, so the existing `/app/data` mount
also persists default tags, output language and AI field instructions. Existing
`/app/config` directory mounts continue to use their own JSON file. No format
conversion or additional mount is required.

Profiles and custom fields remain in `/app/data/settings.yaml`. Field preferences
are sparse overrides: hardcoded defaults → current `HBC_AI_*` environment → saved
JSON values. Reset clears only the JSON overrides, retaining profiles and custom
fields. Invalid settings files are preserved rather than replaced with defaults.

### Homebox API key or legacy login

To enter Companion without a login screen, create a key in **Homebox → Profile → API Keys** and copy its one-time token. Set it on the Companion server:

```dotenv
HBC_HOMEBOX_URL=http://your-homebox-ip:7745
HBC_HOMEBOX_API_KEY=hb_your_homebox_issued_key
```

Restart Companion after changing these values. With Docker Compose, keep the explicit `HBC_HOMEBOX_API_KEY` environment entry shown above and run `docker compose up -d --force-recreate`. A Compose `.env` file supplies interpolation values; it does not automatically pass every variable into the container.

A configured key is used only by the server. The browser receives no Homebox key and has no login, session refresh or Homebox logout action. Missing, empty or whitespace-only keys preserve the username/password flow. An invalid, expired or revoked key shows a connection error with Retry; it never falls back to a password prompt. Removing the key and restarting restores legacy login.

All people who can reach a key-mode deployment act as the key's Homebox owner. Use a dedicated Homebox user with the intended collection permissions and control access through your network or reverse proxy. Browser chat contexts separate conversation history and pending approvals; they are not accounts or access credentials. Existing contextless chats and scan drafts remain stored, but are not loaded automatically into a newly verified context. Clearing browser data creates a new chat context. Server chat state remains in memory with its existing TTL and requires a single worker for consistent conversations.

New API keys created by Homebox v0.27 expire after 30 days when no expiry is
chosen. An upgrade does not retroactively expire existing non-expiring keys.
Check the chosen expiry when creating a key and rotate it before that date.
Companion does not renew keys automatically, so keep the rotation procedure:
create a replacement, update the server environment, restart Companion and
verify its connection, then revoke the old key in Homebox.

Homebox requires its own stable `HBOX_AUTH_API_KEY_PEPPER` of at least 32 bytes;
changing it invalidates issued keys. Configure it on **Homebox**, never on
Companion. See the [Homebox v0.27 configuration documentation](https://github.com/sysadminsmedia/homebox/blob/v0.27.0/docs/src/content/docs/en/quick-start/configure/index.mdx).

### Shared settings

Authenticated Homebox users can manage shared settings, AI model profiles and custom fields. In API-key mode, access uses the configured key's Homebox identity. Homebox credentials are revalidated when accessing Companion's local settings and logs.

Web logs require an additional operator credential in both authentication modes. Set `HBC_LOG_ACCESS_TOKEN` to a long random value distinct from your Homebox and LLM keys, then restart Companion. Without it, log viewing and downloads are disabled. Enter the token in Settings to unlock logs; the browser keeps it only in page memory and sends it in the `X-Companion-Log-Token` header for log requests. Logout, leaving Settings, or reloading the page clears it. A valid operator token still requires valid Homebox authorization.

New log entries disable diagnostic locals and redact configured credentials and common credential fields before emission. Existing historical log files remain unchanged and are available to authenticated operators. LLM debug logs can contain inventory prompts and responses, so share exports carefully.

When editing an AI profile, leave the API key blank to keep its saved key, including when changing the model or API base URL. A primary profile without a key uses the configured environment default; a fallback without a key inherits the primary key. Set a profile's own key when it needs different credentials.

## ✨ Features

### AI-Powered Detection
- Identifies multiple items in a single photo
- Extracts manufacturer, model, serial number, price when visible
- Suggests tags from your existing Homebox tags
- Multi-language support

### Smart Workflow
- **Multi-image analysis** – Take photos from multiple angles for better accuracy
- **Single-item mode** – Force AI to treat a photo as one item (for sets/kits)
- **AI corrections** – Tell the AI what it got wrong and it re-analyzes
- **Custom thumbnails** – Crop and select the best image for each item

### Location Management
- Browse hierarchical location tree
- Search locations by name
- Scan Homebox QR codes
- Create new locations on the fly

### Customization
- Configure how AI formats each field (name style, description format, etc.)
- Set a default tag for all detected items
- Define custom Homebox fields with AI instructions (the AI populates them during detection)

### Chat Assistant
- **Natural language queries** – Ask questions like "How many items do I have?" or "List my tags"
- **Inventory actions** – Create, update, move, or delete items through conversation
- **Approval workflow** – Review and approve AI-proposed changes before they're applied
- **Streaming responses** – Real-time AI responses with tool execution feedback

<details>
<summary>Available Tools</summary>

The chat assistant has access to 24 tools for interacting with your Homebox inventory:

**Read-Only** (auto-execute):
| Tool | Description |
|------|-------------|
| `list_locations` | List all locations |
| `get_location` | Get location details with children |
| `list_tags` | List all tags |
| `list_items` | List items with filtering/pagination |
| `search_items` | Search items by text query |
| `get_item` | Get full item details |
| `get_item_by_asset_id` | Look up item by asset ID |
| `get_item_path` | Get item's full location path |
| `get_location_tree` | Get hierarchical location tree |
| `get_statistics` | Get inventory statistics |
| `get_statistics_by_location` | Item counts by location |
| `get_statistics_by_tag` | Item counts by tag |
| `get_attachment` | Get attachment content |

**Write** (requires approval):
| Tool | Description |
|------|-------------|
| `create_item` | Create a new item |
| `update_item` | Update item fields |
| `create_location` | Create a new location |
| `update_location` | Update location details |
| `create_tag` | Create a new tag |
| `update_tag` | Update tag details |
| `upload_attachment` | Upload attachment to item |
| `ensure_asset_ids` | Assign asset IDs to all items |

**Destructive** (requires approval):
| Tool | Description |
|------|-------------|
| `delete_item` | Delete an item |
| `delete_location` | Delete a location |
| `delete_tag` | Delete a tag |

</details>

## 🤖 LLM Provider Support

Homebox Companion uses [LiteLLM](https://docs.litellm.ai/) as a Python library to call AI providers. **You don't need to self-host anything** – just get an OpenAI API key from [platform.openai.com](https://platform.openai.com/api-keys) and you're ready to go. We officially support and test with OpenAI GPT models only.

> **Fallback Support:** You can configure a secondary LLM profile in Settings that automatically activates if your primary provider fails.

<details>
<summary>Officially Supported Models</summary>

- **GPT-5.6 Luna** (recommended) – Cheapest and most efficient (use with `reasoning_effort=none`)
- **GPT-5 mini** – Previous default
- **GPT-5 nano** – Fastest response times

</details>

<details>
<summary>Using Other Providers (Experimental)</summary>

You can try other LiteLLM-compatible providers at your own risk. The app checks if your chosen model supports the required capabilities using LiteLLM's API:

**Required capabilities (photo scanning):**
- **Vision** – Checked via `litellm.supports_vision(model)`
- **Structured outputs** – Checked via `litellm.supports_response_schema(model)`

**Required for Chat assistant (in addition to the above):**
- **Function calling** – Checked via `litellm.supports_function_calling(model)`. Models without native tool calling (e.g., `llava`, `moondream`) will work for photo scanning but **not** for the Chat assistant, which relies on tool calls to query your inventory.

**Finding model names:**

Model names are passed directly to LiteLLM. Use the exact names from LiteLLM's documentation:
- [LiteLLM Supported Models](https://docs.litellm.ai/docs/providers)

Common examples:
- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-5.6-luna`
- Anthropic: `claude-sonnet-4-5`, `claude-3-5-sonnet-20241022`

> **Note:** Model names must exactly match LiteLLM's expected format. Typos or incorrect formats will cause errors. Check [LiteLLM's provider documentation](https://docs.litellm.ai/docs/providers) for the correct model names.

**Running Local Models:**

You can run models locally using tools like [Ollama](https://ollama.ai/), [LM Studio](https://lmstudio.ai/), or [vLLM](https://docs.vllm.ai/). See [LiteLLM's Local Server documentation](https://docs.litellm.ai/docs/providers/ollama) for setup instructions.

Once your local server is running, configure the app:

```bash
HBC_LLM_API_KEY=any-value-works-for-local  # Just needs to be non-empty
HBC_LLM_API_BASE=http://localhost:11434     # Your local server URL
HBC_LLM_MODEL=ollama/llava:34b              # Your local model name
HBC_LLM_ALLOW_UNSAFE_MODELS=true            # Required for most local models
```

**Note:** Local models must support vision for photo scanning (e.g., llava, bakllava, moondream). For the **Chat assistant**, the model must also support **function calling** — most vision-only models do not. Check your model's capabilities with `litellm.supports_function_calling("ollama/your-model")`. Performance and accuracy vary widely.

**⚠️ Important:** Other providers (Anthropic, Google, OpenRouter, local models, etc.) are **not officially supported**. If you encounter errors, we may not be able to help. Use at your own risk.

</details>

## ⚙️ Configuration

> **📝 Full reference:** See [`.env.example`](.env.example) for all available environment variables with detailed explanations and examples.

### Essential Settings

For a quick setup, you only need to provide your OpenAI API key. All other settings have sensible defaults.

| Variable | Required | Description |
|----------|----------|-------------|
| `HBC_LLM_API_KEY` | **Yes** | Your OpenAI API key |
| `HBC_HOMEBOX_URL` | No | Your Homebox instance URL (defaults to `http://localhost:7745`) |
| `HBC_HOMEBOX_API_KEY` | No | Homebox-issued key for direct entry; empty retains legacy login. Server-only; restart after changing. |
| `HBC_LINK_BASE_URL` | No | Public URL for Homebox links in chat (defaults to `HBC_HOMEBOX_URL`) |

<details>
<summary>⚙️ Full Configuration Reference</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `HBC_LLM_MODEL` | `gpt-5.6-luna` | Model to use. Supported: `gpt-5.6-luna` (recommended), `gpt-5-nano`. |
| `HBC_LLM_API_BASE` | – | Custom API base URL (for proxies or experimental providers) |
| `HBC_LLM_ALLOW_UNSAFE_MODELS` | `false` | Skip capability validation for unrecognized models |
| `HBC_LLM_TIMEOUT` | `120` | LLM request timeout in seconds |
| `HBC_LLM_STREAM_TIMEOUT` | `300` | Streaming timeout for large responses (e.g., hierarchical views) |
| `HBC_MAX_UPLOAD_SIZE_MB` | `20` | Maximum bytes per file, expressed in MiB; must be positive. |
| `HBC_MAX_REQUEST_SIZE_MB` | `100` | Maximum aggregate API request body in MiB, including all files and multipart overhead; enforced while streaming, before parsing can exceed the limit. Must be positive. |
| `HBC_IMAGE_QUALITY` | `medium` | Image quality for Homebox uploads: `raw`, `high`, `medium`, `low` |

</details>

### Advanced Settings

Requests exceeding the body limit return HTTP 413, including chunked uploads. Missing or malformed legacy bearer credentials are rejected before multipart files are read. Configure matching body and concurrency limits on your reverse proxy to bound simultaneous uploads as well. If legitimate multi-image requests exceed 100 MiB, raise `HBC_MAX_REQUEST_SIZE_MB` deliberately; the per-file limit still applies.

<details>
<summary>Image Quality</summary>

Control compression applied to images uploaded to Homebox. Compression happens server-side during AI analysis to avoid slowing down mobile devices.

| Quality Level | Max Dimension | JPEG Quality | File Size | Use Case |
|--------------|---------------|--------------|-----------|----------|
| `raw` | No limit | Original | Largest | Full quality originals |
| `high` | 2560px | 85% | Large | Best quality, moderate size |
| `medium` | 1920px | 75% | Moderate | **Default** - balanced |
| `low` | 1280px | 60% | Smallest | Faster uploads, smaller storage |

**Example:**
```bash
HBC_IMAGE_QUALITY=high
```

**Note:** This setting only affects images uploaded to Homebox. AI analysis always uses optimized images regardless of this setting.

</details>

<details>
<summary>Capture Limits</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `HBC_CAPTURE_MAX_IMAGES` | `30` | Maximum photos per capture session |
| `HBC_CAPTURE_MAX_FILE_SIZE_MB` | `10` | Maximum file size per image in MB |

**Note:** These are experimental settings. It's advisable to keep the default values to minimize data loss risk during capture sessions.

</details>

<details>
<summary>Rate Limiting</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `HBC_RATE_LIMIT_ENABLED` | `true` | Enable/disable API rate limiting |
| `HBC_RATE_LIMIT_RPM` | `400` | Requests per minute (80% of Tier 1 limit) |
| `HBC_RATE_LIMIT_TPM` | `400000` | Tokens per minute (80% of Tier 1 limit) |
| `HBC_RATE_LIMIT_BURST_MULTIPLIER` | `1.5` | Burst capacity multiplier |

**Note:** Default settings are conservative (80% of OpenAI Tier 1 limits). Only configure if you have a higher-tier account or need to adjust limits.

**Examples for different OpenAI tiers:**
- Tier 2: `HBC_RATE_LIMIT_RPM=4000` `HBC_RATE_LIMIT_TPM=1600000`
- Tier 3: `HBC_RATE_LIMIT_RPM=4000` `HBC_RATE_LIMIT_TPM=3200000`

</details>

<details>
<summary>Server & Logging</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `HBC_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `HBC_SERVER_PORT` | `8000` | Server port |
| `HBC_LOG_LEVEL` | `INFO` | Logging level |
| `HBC_LOG_ACCESS_TOKEN` | Unset | Separate operator token for web logs; unset disables viewing/downloads. Requires valid Homebox authorization too. Restart after changing. |
| `HBC_DISABLE_UPDATE_CHECK` | `false` | Disable update notifications |
| `HBC_MAX_UPLOAD_SIZE_MB` | `20` | Maximum file upload size in MB |
| `HBC_CORS_ORIGINS` | `*` | Explicit allowed origins, comma-separated. Wildcard applies only in legacy mode; key mode defaults to same-origin. |

</details>

<details>
<summary>🔒 Security Considerations (Production)</summary>

When deploying to production, review these security settings:

| Variable | Default | Production Recommendation |
|----------|---------|---------------------------|
| `HBC_CORS_ORIGINS` | `*` | Set to specific origins (e.g., `https://your-domain.com`) |
| `HBC_AUTH_RATE_LIMIT_RPM` | `10` | Login attempts per minute per IP (brute-force protection) |
| `HBC_CHAT_RATE_LIMIT_RPM` | `20` | Chat messages per minute per IP (LLM cost protection) |

**CORS Example:**
```bash
# Allow only your frontend domain
HBC_CORS_ORIGINS=https://inventory.example.com

# Multiple origins (comma-separated)
HBC_CORS_ORIGINS=https://inventory.example.com,https://admin.example.com
```

> **Note:** In legacy mode, `HBC_CORS_ORIGINS=*` allows any origin. API-key mode ignores the wildcard and permits same-origin requests plus explicitly listed origins. For a separate development frontend or reverse proxy, list its browser-facing origin. CORS and request-origin checks do not replace network or proxy access control.

</details>

<details>
<summary>🖨️ Label Printing</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `HBC_PRINT_ENABLED` | `false` | Show a "Print Label" button after items are created |

When enabled, a print button appears on the post-creation screen for each item. Pressing it triggers Homebox's built-in labelmaker, which generates and prints a label via the command configured on your **Homebox server**.

**Homebox server prerequisite:** Set the `HBOX_LABEL_MAKER_PRINT_COMMAND` environment variable on your Homebox instance (e.g., `lp -d MyPrinter %s`). Without it, print requests will fail. See [Homebox documentation](https://github.com/sysadminsmedia/homebox) for details.

</details>

<details>
<summary>AI Output Customization</summary>

Customize how AI formats detected item fields. Set via environment variables or the Settings page (UI takes priority).

| Variable | Description |
|----------|-------------|
| `HBC_AI_OUTPUT_LANGUAGE` | Language for AI output (default: English) |
| `HBC_AI_DEFAULT_TAG_ID` | Tag ID to auto-apply to all items |
| `HBC_AI_NAME` | Custom instructions for item naming |
| `HBC_AI_DESCRIPTION` | Custom instructions for descriptions |
| `HBC_AI_QUANTITY` | Custom instructions for quantity counting |
| `HBC_AI_MANUFACTURER` | Instructions for manufacturer extraction |
| `HBC_AI_MODEL_NUMBER` | Instructions for model number extraction |
| `HBC_AI_SERIAL_NUMBER` | Instructions for serial number extraction |
| `HBC_AI_PURCHASE_PRICE` | Instructions for price extraction |
| `HBC_AI_PURCHASE_FROM` | Instructions for retailer extraction |
| `HBC_AI_NOTES` | Custom instructions for notes |
| `HBC_AI_NAMING_EXAMPLES` | Example names to guide the AI |

</details>

## 💡 Tips

- **Batch more items for faster uploads** – Images are analyzed by AI in parallel (up to 30 simultaneously), so adding more items actually feels faster than one at a time.
- **Include receipts in your photos** – AI can extract purchase price, retailer, and date from receipt images.
- **Multiple angles = better results** – Include close-ups of labels, serial numbers, or barcodes for more accurate detection.
- **Asset IDs** – Enter or scan a numeric Homebox ID, such as `032-303`; leave it blank for automatic assignment. Hyphens and leading zeros are accepted. IDs must fit Homebox’s signed 64-bit integer range. Zero is accepted by Homebox but represents an unassigned ID. Invalid IDs must be corrected before analysis, confirmation, or submission.
- **HTTPS required for QR scanning** – Native camera QR detection only works over HTTPS. On HTTP, a "Take Photo" fallback is available.
- **Use the Settings page** – Customize AI behavior, define custom fields, and manage LLM profiles without restarting.
- **Long press to confirm all** – On the review screen, long-press the confirm button to accept all remaining items at once.

## Development

Target recovery contributions at `dev`. Changes on `dev` are not yet a release;
promotion to `main` and publishing are separate steps.

Use Python 3.14+, Node 26.10.0 (matching CI and the Docker frontend builder),
uv 0.9.17+ (CI and Docker use 0.12.5), and locked installs:

```bash
uv sync --locked
cd frontend
npm ci
cd ..
uv run prek install
```

The pre-commit hook checks staged Python files with Ruff and checks frontend lint
and formatting when frontend files change. It does not modify or stage files.
Use `uv run prek run --all-files` to check the whole repository. Full frontend
validation is `npm --prefix frontend run verify`. Python checks matching CI are:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check --error-on-warning
uv run deptry .
uv run pytest
```

Python uses Ruff formatting and ty for type checking. Vulture remains an occasional manual dead-code review tool:
`uv run vulture --sort-by-size`. Dependency audits run weekly and on dependency PRs, outside local hooks.

The PR and `dev` CI workflow runs Python checks, frontend checks, mocked browser
tests, and disposable Homebox integration tests. See [tests/README.md](tests/README.md)
for local commands and Docker/browser prerequisites. These suites require no paid
LLM calls.

Frontend design tokens and reusable utilities live in `frontend/src/app.css`.
Use the semantic color, typography, spacing, and touch-target tokens when styling
components. Svelte style blocks that use Tailwind directives reference this
stylesheet with `@reference`; ordinary CSS can use its theme variables, such as
`var(--color-primary-500)`. Keep canvas drawing colors in
`frontend/src/lib/utils/canvas-colors.ts` synchronized with these tokens.
Tailwind 4's CSS browser baseline is Safari 16.4+, Chrome 111+, and Firefox 128+.
For workflow ownership, Svelte state, authentication transport, and frontend
styling conventions, see [the frontend architecture guide](docs/frontend-architecture.md).

For a deliberate Python dependency refresh, run `uv sync --upgrade`;
routine installs use the committed lockfile with `uv sync --locked`.
For frontend updates, verify compatibility, update the lockfile, and rerun the
checks and `npm audit`. Dependency updates have no minimum release-age requirement.

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Homebox](https://github.com/sysadminsmedia/homebox) – The inventory system this app extends
- [OpenAI](https://openai.com) – Vision AI capabilities (GPT models)
- [LiteLLM](https://docs.litellm.ai/) – LLM provider abstraction layer
- [FastAPI](https://fastapi.tiangolo.com) & [SvelteKit](https://kit.svelte.dev) – Backend & frontend frameworks
<p align="center"> <a href="https://buymeacoffee.com/duelion" target="_blank" rel="noopener noreferrer"> <img src="https://cdn.buymeacoffee.com/buttons/v2/default-red.png" alt="Buy Me A Coffee" width="125"> </a> </p>
