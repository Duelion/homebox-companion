# Pull Request Documentation

This document describes all changes made to the HomeBox-Companion fork, organized into logical PR groupings for upstream submission.

## Overview

Total: **16 commits** across **6 feature areas**

| PR | Feature Area | Commits | Lines Changed |
|----|--------------|---------|---------------|
| PR 1 | State Management (Crash Recovery) | 2 | ~2,300+ |
| PR 2 | Local AI (Ollama) Integration | 2 | ~2,900+ |
| PR 3 | Multi-Provider AI Config System | 4 | ~1,600+ |
| PR 4 | Vision Enhancements (Grouped Detection) | 1 | ~375 |
| PR 5 | Duplicate Detection by Serial Number | 6 | ~1,800+ |
| PR 6 | Connection Settings Overrides | 1 | ~260 |

---

## PR 1: State Management (Crash Recovery)

### Summary
Adds CSV-backed state management for crash recovery, allowing users to resume interrupted scan sessions.

### Commits
1. `7ab43fb` - feat(state): add CSV-backed state management for crash recovery
2. `6aff86a` - feat(sessions): add crash recovery API and UI components

### Files Changed
**Backend:**
- `src/homebox_companion/core/config.py` - Add data_dir, state_max_retries, state_lock_timeout settings
- `src/homebox_companion/models/session.py` - Session data models (NEW)
- `src/homebox_companion/services/state_manager.py` - StateManager class (NEW, 774 lines)
- `server/api/sessions.py` - Sessions REST API endpoints (NEW, 376 lines)

**Frontend:**
- `frontend/src/lib/api/sessions.ts` - Sessions API client (NEW)
- `frontend/src/lib/components/RecoveryBanner.svelte` - Recovery UI component (NEW)

**Tests:**
- `tests/unit/test_state_manager.py` - Comprehensive unit tests (NEW, 629 lines)

### Features
- Create, recover, and manage scan sessions
- Automatic session state persistence to CSV
- File locking for concurrent access safety
- Image state tracking (pending, processing, completed, failed)
- Retry mechanism for failed image processing
- Session archival and cleanup

### Configuration
```env
HBC_DATA_DIR=./data          # Directory for persistent storage
HBC_STATE_MAX_RETRIES=3      # Max retry attempts for failed processing
HBC_STATE_LOCK_TIMEOUT=10    # Timeout for file locking (seconds)
```

---

## PR 2: Local AI (Ollama) Integration

### Summary
Adds support for local AI processing via Ollama, with automatic GPU detection and model recommendations.

### Commits
1. `3d92bc0` - feat(ollama): add local AI integration with GPU detection
2. `a1c2284` - feat(frontend): add Local AI (Ollama) settings section

### Files Changed
**Backend:**
- `src/homebox_companion/core/config.py` - Add Ollama settings (use_ollama, ollama_url, etc.)
- `src/homebox_companion/providers/ollama.py` - Ollama provider implementation (NEW, 524 lines)
- `src/homebox_companion/services/gpu_detector.py` - GPU detection service (NEW, 480 lines)
- `src/homebox_companion/services/ollama_manager.py` - Ollama lifecycle manager (NEW, 486 lines)
- `server/api/ollama.py` - Ollama REST API endpoints (NEW, 223 lines)

**Frontend:**
- `frontend/src/lib/api/ollama.ts` - Ollama API client (NEW)
- `frontend/src/routes/settings/+page.svelte` - Add Ollama settings section

**Tests:**
- `tests/unit/test_gpu_detector.py` - GPU detection tests (NEW)
- `tests/unit/test_ollama_provider.py` - Ollama provider tests (NEW)

### Features
- Automatic GPU detection (NVIDIA, AMD, Intel, Apple Silicon)
- VRAM-based model recommendations
- Ollama connection testing
- Model listing and pull functionality
- Fallback to cloud AI when Ollama unavailable

### Configuration
```env
HBC_USE_OLLAMA=false              # Enable Ollama
HBC_OLLAMA_INTERNAL=false         # Use embedded Ollama in Docker
HBC_OLLAMA_URL=http://localhost:11434  # External Ollama URL
HBC_OLLAMA_MODEL=minicpm-v        # Model to use
HBC_FALLBACK_TO_CLOUD=true        # Fall back to cloud if Ollama fails
```

---

## PR 3: Multi-Provider AI Configuration System

### Summary
Adds a flexible AI provider configuration system supporting Ollama, OpenAI, Anthropic, and LiteLLM with a unified settings UI.

### Commits
1. `5ceb0f9` - feat(ai-config): add multi-provider AI settings with editable UI
2. `5166fa6` - fix(vision): integrate AI config with vision detection endpoints
3. `521cd4f` - fix(ai-config): improve API key UX and preserve keys on edit
4. `c4f284c` - fix(ai-config): improve error handling and response serialization

### Files Changed
**Backend:**
- `src/homebox_companion/core/ai_config.py` - AI config management (NEW, 243 lines)
- `server/api/ai_config.py` - AI config REST API (NEW, 396 lines)
- `server/api/tools/vision.py` - Integrate AI config with vision endpoints
- `server/dependencies.py` - Add LLM config dependencies

**Frontend:**
- `frontend/src/lib/api/aiConfig.ts` - AI config API client (NEW)
- `frontend/src/routes/settings/+page.svelte` - Add AI provider settings UI

### Features
- Support for 4 AI providers: Ollama, OpenAI, Anthropic, LiteLLM
- Per-provider configuration (API keys, models, timeouts)
- Active provider selection with fallback
- Connection testing for each provider
- Secure API key handling (masked display, optional updates)
- Persistent configuration via JSON file

### API Endpoints
- `GET /api/ai-config` - Get current configuration
- `PUT /api/ai-config` - Update configuration
- `POST /api/ai-config/reset` - Reset to defaults
- `POST /api/ai-config/test-connection` - Test provider connection
- `GET /api/ai-config/provider-defaults/{provider}` - Get provider defaults

---

## PR 4: Vision Enhancements (Grouped Detection)

### Summary
Adds grouped detection capability that automatically identifies when multiple images show the same physical item.

### Commits
1. `9e1605d` - feat(vision): add grouped detection for automatic image grouping

### Files Changed
**Backend:**
- `src/homebox_companion/tools/vision/detector.py` - Add grouped_detect_items function
- `src/homebox_companion/tools/vision/prompts.py` - Add grouped detection prompts
- `src/homebox_companion/tools/vision/models.py` - Add image_indices field to DetectedItem
- `server/api/tools/vision.py` - Add /detect-grouped endpoint
- `server/schemas/vision.py` - Add GroupedDetectionResponse schema

**Frontend:**
- `frontend/src/lib/api/vision.ts` - Add detectGrouped method
- `frontend/src/lib/types/index.ts` - Add GroupedDetectionResponse type

### Features
- Analyze multiple images to identify unique items
- Automatically group images showing the same item (e.g., front/back photos)
- Return image indices for each detected item
- Optimized prompts for grouping accuracy

### API Endpoint
```
POST /api/vision/detect-grouped
Content-Type: multipart/form-data

Response: {
  "items": [
    { "name": "DeWalt Drill", "image_indices": [0, 2, 3], ... }
  ],
  "total_images": 4,
  "message": "Detected 2 unique items across 4 images"
}
```

---

## PR 5: Duplicate Detection by Serial Number

### Summary
Adds duplicate detection to warn users before adding items that may already exist in Homebox, based on serial number matching.

### Commits
1. `c5b574d` - feat(duplicates): add serial number duplicate detection
2. `02688be` - feat(settings): add toggle to enable/disable duplicate detection
3. `4fd4484` - fix(duplicates): fetch individual item details for serial numbers
4. `fb152b4` - feat(duplicates): add persistent index with differential updates
5. `cfc49b0` - fix(duplicates): improve error handling and UI messaging
6. `8af6515` - fix(duplicates): handle Homebox string asset IDs correctly

### Files Changed
**Backend:**
- `src/homebox_companion/services/duplicate_detector.py` - DuplicateDetector service (NEW, ~600 lines)
- `src/homebox_companion/core/app_preferences.py` - App preferences (NEW)
- `server/api/items.py` - Add duplicate check endpoints
- `server/api/app_preferences.py` - App preferences API (NEW)
- `server/schemas/items.py` - Add duplicate detection schemas
- `server/dependencies.py` - Add DuplicateDetectorHolder singleton

**Frontend:**
- `frontend/src/lib/api/items.ts` - Add checkDuplicates, getDuplicateIndexStatus, rebuildDuplicateIndex
- `frontend/src/lib/api/settings.ts` - Add appPreferences API
- `frontend/src/lib/components/DuplicateWarningBanner.svelte` - Warning UI (NEW)
- `frontend/src/lib/workflows/scan.svelte.ts` - Integrate duplicate checking
- `frontend/src/routes/review/+page.svelte` - Show per-item warnings
- `frontend/src/routes/summary/+page.svelte` - Show summary warnings
- `frontend/src/routes/settings/+page.svelte` - Add Behavior Settings section

### Features
- Persistent serial number index (survives container restarts)
- Differential updates using asset IDs (only fetch new items on startup)
- Manual index rebuild via Settings UI
- Incremental updates when items are created
- Non-blocking warnings in review and submission phases
- Toggle to enable/disable duplicate detection
- Handles Homebox's string-formatted asset IDs (e.g., "000-004")

### API Endpoints
- `POST /api/items/check-duplicates` - Check items for duplicates
- `GET /api/items/duplicate-index/status` - Get index status
- `POST /api/items/duplicate-index/rebuild` - Rebuild index
- `GET /api/settings/app-preferences` - Get app preferences
- `PUT /api/settings/app-preferences` - Update app preferences

---

## PR 6: Connection Settings Overrides

### Summary
Allows users to customize Homebox URL and image quality from the Settings UI without modifying environment variables.

### Commits
1. `1bfc481` - feat(settings): add Connection Settings with editable URL and quality

### Files Changed
**Backend:**
- `src/homebox_companion/core/app_preferences.py` - Add homebox_url_override, image_quality_override
- `server/api/config.py` - Add effective URL/quality helpers

**Frontend:**
- `frontend/src/lib/api/client.ts` - Use effective URL from config
- `frontend/src/lib/api/settings.ts` - Add override fields to AppPreferences
- `frontend/src/routes/settings/+page.svelte` - Add Connection Settings section

### Features
- Editable Homebox URL (overrides HBC_HOMEBOX_URL)
- Selectable image quality (Raw, High, Medium, Low)
- Changes persist across restarts
- Clear indication of current values vs. environment defaults

---

## Branch Creation Commands

To create feature branches for each PR:

```bash
# Ensure upstream is up to date
git fetch upstream

# PR 1: State Management
git checkout -b pr/state-management upstream/main
git cherry-pick 7ab43fb 6aff86a

# PR 2: Ollama Integration
git checkout -b pr/ollama-integration upstream/main
git cherry-pick 3d92bc0 a1c2284

# PR 3: AI Config System
git checkout -b pr/ai-config-system upstream/main
git cherry-pick 5ceb0f9 5166fa6 521cd4f c4f284c

# PR 4: Grouped Detection
git checkout -b pr/grouped-detection upstream/main
git cherry-pick 9e1605d

# PR 5: Duplicate Detection
git checkout -b pr/duplicate-detection upstream/main
git cherry-pick c5b574d 02688be 4fd4484 fb152b4 cfc49b0 8af6515

# PR 6: Connection Settings
git checkout -b pr/connection-settings upstream/main
git cherry-pick 1bfc481
```

---

## Recommended PR Order

1. **PR 1: State Management** - Foundation for crash recovery (no dependencies)
2. **PR 2: Ollama Integration** - Standalone local AI feature
3. **PR 3: AI Config System** - Depends slightly on PR 2 concepts but can stand alone
4. **PR 4: Grouped Detection** - Standalone vision enhancement
5. **PR 6: Connection Settings** - Small, standalone settings feature
6. **PR 5: Duplicate Detection** - Largest PR, can be submitted last

---

## Testing Notes

All features include:
- Backend unit tests where applicable
- Manual testing on Windows and Docker environments
- Backward compatibility with existing environment variables
- Demo mode support for testing without real Homebox instance
