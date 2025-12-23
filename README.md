<h1 align="center" style="margin-top: -10px;"></h1>

<div align="center">
  <img src=".github/assets/images/homebox-companion-icon.png" height="200"/>
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

<div align="center">
  <a href="https://demo.hbcompanion.duelion.com/" target="_blank">
    <img src=".github/assets/images/demo_button.png" alt="Try Live Demo" width="300">
  </a>
  <br>
  <sub><i>View results in the <a href="https://demo.hb.duelion.com/">Homebox demo instance</a></i></sub>
</div>

## 🔄 How It Works

```mermaid
flowchart LR
    A[🔐 Login<br/>Homebox] --> B[📍 Select<br/>Location]
    B --> C[📸 Capture<br/>Photos]
    C --> D[✏️ Review &<br/>Edit Items]
    D --> E[✅ Submit to<br/>Homebox]
    
    B -.-> B1[/Browse, search,<br/>or scan QR/]
    C -.-> C1[/AI analyzes with<br/>OpenAI GPT-5/]
    D -.-> D1[/Edit names,<br/>quantities, labels/]
    
```

1. **Login** – Authenticate with your existing Homebox credentials
2. **Select Location** – Browse the location tree, search, or scan a Homebox QR code
3. **Capture Photos** – Take or upload photos of items (supports multiple photos per item)
4. **AI Detection** – AI vision (via LiteLLM) identifies items, quantities, and metadata
5. **Review & Edit** – Adjust AI suggestions, merge items, or ask AI to correct mistakes
6. **Submit** – Items are created in your Homebox inventory with photos attached

https://github.com/user-attachments/assets/fcaae316-f4fa-462e-8ed2-d0d7e82145fd

## 💰 OpenAI Cost Estimates

Prices as of **2025-12-10**, using OpenAI’s published pricing for GPT-5 mini and GPT-5 nano.   

**Per-token pricing (per 1M tokens):**

- **GPT-5 nano**
  - Input: **$0.0500 / 1M tokens**
  - Output: **$0.4000 / 1M tokens**

- **GPT-5 mini**
  - Input: **$0.2500 / 1M tokens**
  - Output: **$2.0000 / 1M tokens**

All estimates below are based on measured token usage from this app’s production prompt with 1–5 images per call.

### Estimated API cost for Homebox Companion

#### GPT-5 mini

| Images per call | Cost / 1 call | Cost / 100 calls | Cost / 500 calls | Cost / 1,000 calls |
|----------------:|--------------:|-----------------:|-----------------:|-------------------:|
| 1 | **$0.0026** | **$0.2580** | **$1.2900** | **$2.5800** |
| 2 | **$0.0032** | **$0.3236** | **$1.6180** | **$3.2360** |
| 3 | **$0.0031** | **$0.3130** | **$1.5650** | **$3.1300** |
| 4 | **$0.0037** | **$0.3672** | **$1.8360** | **$3.6720** |
| 5 | **$0.0041** | **$0.4108** | **$2.0540** | **$4.1080** |

#### GPT-5 nano

| Images per call | Cost / 1 call | Cost / 100 calls | Cost / 500 calls | Cost / 1,000 calls |
|----------------:|--------------:|-----------------:|-----------------:|-------------------:|
| 1 | **$0.0008** | **$0.0801** | **$0.4005** | **$0.8010** |
| 2 | **$0.0008** | **$0.0781** | **$0.3907** | **$0.7815** |
| 3 | **$0.0010** | **$0.0958** | **$0.4788** | **$0.9577** |
| 4 | **$0.0014** | **$0.1386** | **$0.6929** | **$1.3858** |
| 5 | **$0.0013** | **$0.1264** | **$0.6320** | **$1.2639** |

> Although gpt-5-nano may be smaller and faster on a per-token basis, our testing shows that it generates significantly more tokens to complete the same task, ultimately offsetting any apparent speed advantage.

## 📋 Requirements

Before you start, you'll need:

- **An OpenAI API key** – Get one at [platform.openai.com](https://platform.openai.com/api-keys)
- **A Homebox instance** – Your own [Homebox](https://github.com/sysadminsmedia/homebox) server, or use the [demo server](#try-with-demo-server) to test

## 🚀 Quick Start

### Try with Demo Server

Want to try it out without setting up Homebox? Use the public demo server:

```bash
docker run -p 8000:8000 \
  -e HBC_LLM_API_KEY=sk-your-key \
  -e HBC_HOMEBOX_URL=https://demo.homebox.software \
  ghcr.io/duelion/homebox-companion:latest
```

Open `http://localhost:8000` and login with `demo@example.com` / `demo`

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
    ports:
      - 8000:8000
```

```bash
docker compose up -d
```

Open `http://localhost:8000` in your browser.

> **Tip:** If Homebox runs on the same machine but outside Docker, use `http://host.docker.internal:PORT` as the URL.

### Run from Source

Alternative to Docker if you prefer running directly on your system.

**Prerequisites:** Python 3.12+, Node.js 20+, [uv](https://docs.astral.sh/uv/)

#### Linux / macOS

```bash
# Clone and install
git clone https://github.com/Duelion/homebox-companion.git
cd homebox-companion
uv sync

# Build frontend
cd frontend && npm install && npm run build && cd ..
mkdir -p server/static && cp -r frontend/build/* server/static/

# Configure - copy example and edit
cp .env.example .env
# Edit .env and set your HBC_LLM_API_KEY

# Run
uv run python -m server.app
```

Open `http://localhost:8000` in your browser.

> **Note:** See `.env.example` for all available configuration options including AI customization settings.

## ✨ Features

### AI-Powered Detection
- Identifies multiple items in a single photo
- Extracts manufacturer, model, serial number, price when visible
- Suggests labels from your existing Homebox labels
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
- Set a default label for all detected items
- Export settings as environment variables for Docker persistence

## 🤖 LLM Provider Support

Homebox Companion uses [LiteLLM](https://docs.litellm.ai/) for AI capabilities. While LiteLLM supports many providers (OpenAI, Anthropic, Google, OpenRouter, etc.), **we only officially support and test with OpenAI GPT models**.

### Officially Supported Models

- **GPT-5 mini** (default) – Recommended for best balance of speed and accuracy
- **GPT-5 nano**

### Using Other Providers (Experimental)

You can try other LiteLLM-compatible providers at your own risk. The app checks if your chosen model supports the required capabilities using LiteLLM's API:

**Required capabilities:**
- **Vision** – Checked via `litellm.supports_vision(model)`
- **Structured outputs** – Checked via `litellm.supports_response_schema(model)`

**Finding model names:**

Model names are passed directly to LiteLLM. Use the exact names from LiteLLM's documentation:
- [LiteLLM Supported Models](https://docs.litellm.ai/docs/providers)

Common examples:
- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-5-mini`
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

**Note:** Local models must support vision (e.g., llava, bakllava, moondream). Performance and accuracy vary widely.

**⚠️ Important:** Other providers (Anthropic, Google, OpenRouter, local models, etc.) are **not officially supported**. If you encounter errors, we may not be able to help. Use at your own risk.

## ⚙️ Configuration

> **📝 Full reference:** See [`.env.example`](.env.example) for all available environment variables with detailed explanations and examples.

### Essential Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HBC_LLM_API_KEY` | **Yes** | – | Your OpenAI API key (or other provider key if experimenting) |
| `HBC_LLM_MODEL` | No | `gpt-5-mini` | Model to use. Officially supported: `gpt-5-mini`, `gpt-5-nano`. See [LiteLLM docs](https://docs.litellm.ai/docs/providers) for other models. |
| `HBC_LLM_API_BASE` | No | – | Custom API base URL (for proxies or experimental providers) |
| `HBC_LLM_ALLOW_UNSAFE_MODELS` | No | `false` | Skip capability validation for unrecognized models |
| `HBC_LLM_TIMEOUT` | No | `120` | LLM request timeout in seconds |
| `HBC_HOMEBOX_URL` | No | Demo server | Your Homebox instance URL |
| `HBC_IMAGE_QUALITY` | No | `medium` | Image quality for Homebox uploads: `raw`, `high`, `medium`, `low` |

**Legacy variables:** `HBC_OPENAI_API_KEY` and `HBC_OPENAI_MODEL` still work but are deprecated.

### Advanced Settings

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
<summary>Server & Logging</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `HBC_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `HBC_SERVER_PORT` | `8000` | Server port |
| `HBC_LOG_LEVEL` | `INFO` | Logging level |
| `HBC_DISABLE_UPDATE_CHECK` | `false` | Disable update notifications |
| `HBC_MAX_UPLOAD_SIZE_MB` | `20` | Maximum file upload size in MB |
| `HBC_CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated or `*`) |

</details>

<details>
<summary>AI Output Customization</summary>

Customize how AI formats detected item fields. Set via environment variables or the Settings page (UI takes priority).

| Variable | Description |
|----------|-------------|
| `HBC_AI_OUTPUT_LANGUAGE` | Language for AI output (default: English) |
| `HBC_AI_DEFAULT_LABEL_ID` | Label ID to auto-apply to all items |
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

**Tip:** The Settings page has an "Export as Environment Variables" button.

</details>

## 💡 Tips

- **HTTPS recommended for QR scanning** – Native camera QR detection only works over HTTPS. On HTTP, a "Take Photo" fallback is available.
- **Multiple photos = better results** – Include close-ups of labels, serial numbers, or receipts for more accurate detection.

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Homebox](https://github.com/sysadminsmedia/homebox) – The inventory system this app extends
- [OpenAI](https://openai.com) – Vision AI capabilities (GPT models)
- [LiteLLM](https://docs.litellm.ai/) – LLM provider abstraction layer
- [FastAPI](https://fastapi.tiangolo.com) & [SvelteKit](https://kit.svelte.dev) – Backend & frontend frameworks
<p align="center"> <a href="https://buymeacoffee.com/duelion" target="_blank" rel="noopener noreferrer"> <img src="https://cdn.buymeacoffee.com/buttons/v2/default-red.png" alt="Buy Me A Coffee" width="125"> </a> </p>
