<h1 align="center" style="margin-top: -10px;"></h1>

<div align="center">
  <a href="#"><img src=".github/assets/images/homebox-companion-icon.png" height="200"/></a>
</div>

<h1 align="center" style="margin-top: -10px;"> Homebox Companion (Enhanced Fork) </h1>

> **Fork of [Duelion/homebox-companion](https://github.com/Duelion/homebox-companion)** with privacy-first enhancements.
> Not affiliated with the Homebox project. This is an unofficial third-party companion app.

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

## Fork Enhancements

This fork adds the following features while maintaining full compatibility with the upstream project:

| Feature | Description |
|---------|-------------|
| **Multi-Provider AI** | Switch between OpenAI, Anthropic, and Ollama from the Settings UI |
| **Local AI (Ollama)** | Privacy-first local processing - images never leave your network |
| **Duplicate Detection** | Warns when scanned items match existing serial numbers |
| **In-App Configuration** | Configure everything in the UI - no YAML/env vars required |
| **Simplified Deployment** | Just mount a volume, configure in browser |

See the [Wiki](../../wiki) for detailed documentation on all features.

---

## Quick Start (This Fork)

### Simplified Docker Deployment

```yaml
# docker-compose.yml
services:
  homebox-companion:
    image: ghcr.io/synssins/homebox-companion:latest
    container_name: homebox-companion
    restart: always
    ports:
      - 8000:8000
    volumes:
      - companion-data:/data

volumes:
  companion-data:
```

```bash
docker compose up -d
```

Open `http://localhost:8000` and configure everything in the Settings page:
1. **Connection Settings** - Enter your Homebox URL
2. **AI Provider** - Configure OpenAI, Anthropic, or Ollama
3. **Behavior Settings** - Enable duplicate detection

> **No environment variables required!** All configuration is done in the browser and persists in the data volume.

### Using Local AI (Ollama)

For complete privacy with no cloud dependencies:

```yaml
services:
  homebox-companion:
    image: ghcr.io/synssins/homebox-companion:latest
    ports:
      - 8000:8000
    volumes:
      - companion-data:/data

  ollama:
    image: ollama/ollama:latest
    ports:
      - 11434:11434
    volumes:
      - ollama-models:/root/.ollama

volumes:
  companion-data:
  ollama-models:
```

Then in Settings > AI Provider:
1. Enable Ollama
2. Set URL to `http://ollama:11434`
3. Select a vision model (e.g., `minicpm-v`)

Pull the model first: `docker exec ollama ollama pull minicpm-v`

---

## How It Works

```mermaid
flowchart LR
    A[Login<br/>Homebox] --> B[Select<br/>Location]
    B --> C[Capture<br/>Photos]
    C --> D[Review &<br/>Edit Items]
    D --> E[Submit to<br/>Homebox]

    C -.-> C1[/AI analyzes with<br/>your choice of provider/]
    D -.-> D1[/Duplicate warnings<br/>shown here/]
```

1. **Login** - Authenticate with your existing Homebox credentials
2. **Select Location** - Browse the location tree, search, or scan a Homebox QR code
3. **Capture Photos** - Take or upload photos of items (supports multiple photos per item)
4. **AI Detection** - AI vision identifies items, quantities, and metadata
5. **Review & Edit** - Adjust AI suggestions, see duplicate warnings
6. **Submit** - Items are created in your Homebox inventory with photos attached

---

## Fork-Specific Features

### Multi-Provider AI Configuration

Configure and switch between AI providers directly in the Settings UI:

- **OpenAI** - GPT-4o, GPT-4o-mini (cloud, paid)
- **Anthropic** - Claude models (cloud, paid)
- **Ollama** - Local models like minicpm-v, llava (free, private)

Each provider can be enabled/disabled independently. The active provider is shown in a badge on the Settings page.

### Duplicate Detection

Prevents accidentally creating duplicate inventory entries:

- Builds an index of all serial numbers in your Homebox
- Checks scanned items against the index during review
- Shows warning banner: "May be duplicate - matches [Item Name]"
- Non-blocking - you can still add items if desired
- Persistent index survives container restarts

Enable in Settings > Behavior Settings.

### In-App Settings

All configuration moved from environment variables to the UI:

| Setting | Location |
|---------|----------|
| Homebox URL | Settings > Connection |
| Image Quality | Settings > Connection |
| AI Provider/Keys | Settings > AI Provider |
| Duplicate Detection | Settings > Behavior |

Settings persist in `/data` - just mount the volume and configure once.

---

## Original Features

All features from the upstream project are preserved:

### AI-Powered Detection
- Identifies multiple items in a single photo
- Extracts manufacturer, model, serial number, price when visible
- Suggests labels from your existing Homebox labels
- Multi-language support

### Smart Workflow
- **Multi-image analysis** - Take photos from multiple angles for better accuracy
- **Single-item mode** - Force AI to treat a photo as one item (for sets/kits)
- **AI corrections** - Tell the AI what it got wrong and it re-analyzes
- **Custom thumbnails** - Crop and select the best image for each item

### Location Management
- Browse hierarchical location tree
- Search locations by name
- Scan Homebox QR codes
- Create new locations on the fly

### Chat Assistant
- **Natural language queries** - Ask questions like "How many items do I have?"
- **Inventory actions** - Create, update, move, or delete items through conversation
- **Approval workflow** - Review AI-proposed changes before they're applied

<details>
<summary>Available Chat Tools</summary>

The chat assistant has access to 21 tools for interacting with your Homebox inventory:

**Read-Only** (auto-execute):
| Tool | Description |
|------|-------------|
| `list_locations` | List all locations |
| `get_location` | Get location details with children |
| `list_labels` | List all labels |
| `list_items` | List items with filtering/pagination |
| `search_items` | Search items by text query |
| `get_item` | Get full item details |
| `get_item_by_asset_id` | Look up item by asset ID |
| `get_item_path` | Get item's full location path |
| `get_location_tree` | Get hierarchical location tree |
| `get_statistics` | Get inventory statistics |
| `get_statistics_by_location` | Item counts by location |
| `get_statistics_by_label` | Item counts by label |
| `get_attachment` | Get attachment content |

**Write** (requires approval):
| Tool | Description |
|------|-------------|
| `create_item` | Create a new item |
| `update_item` | Update item fields |
| `create_location` | Create a new location |
| `update_location` | Update location details |
| `create_label` | Create a new label |
| `update_label` | Update label details |
| `upload_attachment` | Upload attachment to item |
| `ensure_asset_ids` | Assign asset IDs to all items |

**Destructive** (requires approval):
| Tool | Description |
|------|-------------|
| `delete_item` | Delete an item |
| `delete_location` | Delete a location |
| `delete_label` | Delete a label |

</details>

---

## Configuration

### Environment Variables (Optional)

While this fork allows full configuration via the UI, environment variables still work for automated deployments:

<details>
<summary>Essential Settings</summary>

| Variable | Required | Description |
|----------|----------|-------------|
| `HBC_LLM_API_KEY` | No* | Your OpenAI API key (*can configure in UI) |
| `HBC_HOMEBOX_URL` | No* | Your Homebox instance URL (*can configure in UI) |

</details>

<details>
<summary>Full Configuration Reference</summary>

| Variable | Default | Description |
|----------|---------|-------------|
| `HBC_LLM_MODEL` | `gpt-4o-mini` | Model to use for cloud AI |
| `HBC_LLM_API_BASE` | - | Custom API base URL |
| `HBC_LLM_TIMEOUT` | `120` | LLM request timeout in seconds |
| `HBC_IMAGE_QUALITY` | `medium` | Image quality: `raw`, `high`, `medium`, `low` |
| `HBC_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `HBC_SERVER_PORT` | `8000` | Server port |
| `HBC_LOG_LEVEL` | `INFO` | Logging level |
| `HBC_DATA_DIR` | `/data` | Data directory for settings persistence |

</details>

---

## Tips

- **Use local AI for privacy** - Ollama keeps all image processing on your network
- **Enable duplicate detection** - Prevents accidentally re-adding items you already have
- **Batch more items** - Images are analyzed in parallel, so more items = faster per-item
- **Include receipts** - AI can extract purchase price, retailer, and date
- **Multiple angles** - Include close-ups of labels, serial numbers for accuracy
- **Long press to confirm all** - On review screen, long-press confirm to accept all items

---

## Compatibility

- **Upstream compatible** - All original features work unchanged
- **Homebox v0.21+** - Tested with recent Homebox versions
- **Environment variables** - All original env vars still work
- **API compatible** - No breaking changes to API endpoints

---

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **[Duelion/homebox-companion](https://github.com/Duelion/homebox-companion)** - Original project this fork is based on
- [Homebox](https://github.com/sysadminsmedia/homebox) - The inventory system this app extends
- [OpenAI](https://openai.com) - Vision AI capabilities (GPT models)
- [Ollama](https://ollama.ai) - Local AI runtime
- [LiteLLM](https://docs.litellm.ai/) - LLM provider abstraction layer
- [FastAPI](https://fastapi.tiangolo.com) & [SvelteKit](https://kit.svelte.dev) - Backend & frontend frameworks

---

<p align="center">
  <i>Original project by <a href="https://github.com/Duelion">Duelion</a> -
  <a href="https://buymeacoffee.com/duelion" target="_blank">Buy them a coffee</a></i>
</p>
