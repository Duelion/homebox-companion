# Release Notes - Version 1.14.3

**Release Date:** December 2025

This release focuses on **enhanced logging capabilities**, **UI/UX improvements**, and **code quality refinements** across both backend and frontend components.

---

## 🎯 Highlights

### Enhanced Logging System
Comprehensive logging improvements throughout the application with better error tracking, log rotation by size, and improved debugging capabilities for production environments.

### Improved User Interface
Better accessibility on iOS devices with safe area padding, auto-scrolling fullscreen logs, and refined icon styling in the thumbnail editor.

### Code Quality Improvements
Clearer field instructions and simplified notes guidance for better AI-generated content quality.

---

## ✨ New Features

### Logging Enhancements
- **Log Rotation by Size:** Log files now rotate when reaching 50 MB (in addition to daily rotation) for better disk space management
- **Auto-Scrolling Fullscreen Logs:** Logs automatically scroll to the most recent entries when the fullscreen log view is opened or refreshed
- **Enhanced Error Tracking:** Updated error handling to use `logger.exception` for improved stack trace visibility across all API endpoints
- **Informational Logging:** Added logging for significant actions including field preference updates and API shutdown events

### UI/UX Improvements
- **iOS Safe Area Support:** Header layout now includes safe area padding for better compatibility with iOS notches and home indicators
- **Improved Thumbnail Editor:** Updated SVG icons for better consistency, clarity, and visual appeal
- **Enhanced Accessibility:** Restructured header layout for improved accessibility and simplified markup

---

## 🔧 Technical Improvements

### Backend
- **Comprehensive Logging Integration:** Integrated loguru logging across multiple modules:
  - `server/api/field_preferences.py` - Field preference operations logging
  - `server/api/items.py` - Item operations error handling
  - `server/api/tools/vision.py` - Vision tool processing logs
  - `server/app.py` - Application lifecycle logging
- **Log Management:** Log rotation configuration updated from time-based to size-based (50 MB) with 7-day retention

### Frontend
- **Auto-Scroll Implementation:** Added reactive state management for fullscreen logs container
- **Header Refactoring:** Simplified header structure while maintaining full functionality
- **Icon Optimization:** Refined SVG icons in ThumbnailEditor component for better consistency

### Code Quality
- **Notes Instructions:** Revised and simplified notes field instructions across the application
  - Added GOOD/BAD examples for clearer defect reporting guidance
  - Ensured consistency in notes formatting
  - Updated default field preferences
  - Updated tests to reflect clearer instructions

---

## 🐛 Bug Fixes

- **Error Handling:** Improved exception logging across API endpoints for better troubleshooting
- **Header Layout:** Fixed header markup inconsistencies that could affect mobile responsiveness

---

## 📦 Files Changed

**Backend (6 files):**
- `server/api/field_preferences.py` - Added comprehensive logging
- `server/api/items.py` - Enhanced error handling
- `server/api/tools/vision.py` - Improved logging
- `server/app.py` - Added lifecycle logging
- `src/homebox_companion/core/logging.py` - Updated log rotation strategy
- `src/homebox_companion/core/field_preferences.py` - Updated notes instructions

**Frontend (3 files):**
- `frontend/src/routes/+layout.svelte` - Header accessibility improvements
- `frontend/src/routes/settings/+page.svelte` - Auto-scroll for logs
- `frontend/src/lib/components/ThumbnailEditor.svelte` - Icon refinements

**Tests (2 files):**
- `src/homebox_companion/ai/prompts.py` - Simplified notes instructions
- `tests/test_prompts.py` - Updated tests for new instructions

**Total:** 12 files changed, 88 insertions(+), 46 deletions(-)

---

## 🔄 Migration Notes

No breaking changes in this release. All improvements are backward compatible.

**Note:** Log files will now rotate at 50 MB instead of only daily. Existing log files will continue to work and rotate according to the new rules.

---

## 🚀 Getting Started

### Installation

```bash
# Using Docker
docker pull ghcr.io/duelion/homebox-companion:1.14.3

# Using pip
pip install homebox-companion==1.14.3

# From source with uv
git clone https://github.com/Duelion/homebox-companion.git
cd homebox-companion
git checkout v1.14.3
uv sync
```

### Required Environment Variables

```bash
HBC_OPENAI_API_KEY=sk-your-key          # Required
HBC_HOMEBOX_URL=https://demo.homebox.software  # Optional, defaults to demo
```

### Important Notes

- **HTTPS Required:** Camera access for QR scanning requires HTTPS in production environments
- **OpenAI Models:** This version uses GPT-5 models (`gpt-5-mini` or `gpt-5-nano`)
- **Log Files:** Logs are now stored in `logs/` directory with 50 MB rotation and 7-day retention

---

## 📝 Known Issues

None at this time. Please report issues at: https://github.com/Duelion/homebox-companion/issues

---

## 📋 Full Changelog

### Commits in this Release

1. **refactor: enhance logging throughout the application** (30f5611)
   - Integrated loguru for improved logging capabilities across multiple modules
   - Updated error handling to use logger.exception for better stack trace visibility
   - Added informational logs for significant actions
   - Adjusted logging configuration to rotate log files based on size

2. **feat: add auto-scroll functionality for fullscreen logs** (c2fd398)
   - Introduced state variable for fullscreen logs container
   - Implemented effect to scroll to bottom when logs are opened or refreshed

3. **refactor: restructure header layout for improved accessibility** (042bcd0)
   - Updated header structure with safe area padding for iOS compatibility
   - Simplified header markup while maintaining functionality

4. **refactor: update notes instructions for clarity and consistency** (ff0258f)
   - Revised notes instructions with GOOD/BAD examples
   - Ensured consistency in notes formatting across the application

5. **refactor: update SVG icons in ThumbnailEditor for consistency and clarity** (06be9b6)
   - Enhanced icon visual consistency in thumbnail editing interface

6. **refactor: update SVG icons in ThumbnailEditor for improved styling** (1ea981b)
   - Further refined icon styling for better user experience

---

## 🙏 Acknowledgments

Special thanks to @fsozale for the comprehensive logging enhancements, UI improvements, and documentation refinements in this release.

---

## 🔗 Resources

- **Repository:** https://github.com/Duelion/homebox-companion
- **Documentation:** https://github.com/Duelion/homebox-companion#readme
- **Issue Tracker:** https://github.com/Duelion/homebox-companion/issues
- **Homebox Project:** https://github.com/sysadminsmedia/homebox

