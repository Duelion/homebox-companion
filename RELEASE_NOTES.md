# Release Notes - Version 1.13.3

**Release Date:** December 2025

This release focuses on **significant QR scanner improvements** for iOS and cross-browser compatibility, enhanced **logging capabilities**, and critical **bug fixes** for navigation state management.

---

## 🎯 Highlights

### Major iOS QR Scanner Improvements
Fixed multiple critical issues preventing QR scanning from working reliably on iOS devices, particularly iPhones. The QR scanner now works seamlessly with iPhone photos, Safari/Firefox browsers, and handles iOS-specific image formats correctly.

### Enhanced Logging & Diagnostics
Improved logging interface with colorization, auto-scrolling, fullscreen modal view, and downloadable log files for easier troubleshooting and debugging.

### Navigation & State Management Fixes
Resolved issues where location state wasn't being cleared properly and analysis processes could become orphaned after cancellation.

---

## ✨ New Features

### Log Management
- **Log Download:** New API endpoint and download button to export log files for debugging
- **Fullscreen Logs Modal:** View logs in an expandable fullscreen interface for better visibility
- **Colorized Log Output:** Enhanced log readability with color-coded log levels
- **Auto-Scrolling Logs:** Logs automatically scroll to the most recent entries
- **Dynamic Log Level:** Logging configuration now respects dynamic log level from settings

### QR Scanner Enhancements
- **Camera Fallback:** QR fallback now opens camera capture directly instead of file picker for better UX
- **File Upload Fallback:** Added file upload fallback when camera access fails, with retry functionality
- **HTTPS Requirement Documentation:** Added clear documentation about HTTPS requirement for camera access

---

## 🐛 Bug Fixes

### QR Scanner - iOS & Cross-Browser Compatibility
- **iPhone Photo Scaling:** Fixed QR scanner failing on iPhone photos (12.2 MP) by scaling images to max 1280px before processing
  - Root cause: qr-scanner library fails on images > ~2 megapixels
  - Simplified QrScanner.svelte from 573 to 295 lines by removing unused rotation/EXIF code
  
- **iOS HEIC Format Support:** Fixed 'No QR code found' errors with iPhone photos by forcing JPEG/PNG/WebP formats instead of HEIC
  - iOS now automatically converts HEIC to compatible format on upload

- **Safari/Firefox Camera Detection:** Fixed false 'No camera found' error on Safari/Firefox
  - Removed unreliable `QrScanner.hasCamera()` pre-check that blocked browsers
  - Added proper `isSecureContext` check with HTTPS-specific error messages
  - Improved error messages for each camera error type (NotAllowed, NotFound, etc.)

- **Image Processing:** Prevented QR scanner timeout by scaling down large images before processing

### Navigation & State Management
- **Orphaned Analysis Prevention:** Fixed issue where canceling analysis could leave processes running and cause unintended redirects
- **Location State Cleanup:** Fixed location state not being cleared when navigating back or logging out

---

## 🔧 Technical Improvements

### Code Quality
- **QR Scanner Refactoring:** Simplified QrScanner.svelte by removing ~280 lines of unused EXIF rotation code and debug logging
- **Removed Debug Code:** Cleaned up temporary image profiling and debug logging added during QR investigation

### Documentation
- **Unofficial Status:** Clarified in README that this is an unofficial companion app for Homebox

---

## 📦 Package Updates
- Cleaned up unnecessary `peer: true` flag from package-lock.json

---

## 🔄 Migration Notes

No breaking changes in this release. All improvements are backward compatible.

---

## 🙏 Acknowledgments

Special thanks to @fsozale for contributions to the logging enhancements and styling improvements.

---

## 📋 Full Changelog

For a complete list of changes, see the commit history on GitHub.

---

## 🚀 Getting Started

### Installation

```bash
# Using Docker
docker pull ghcr.io/duelion/homebox-companion:latest

# Using pip
pip install homebox-companion==1.13.3

# From source with uv
git clone https://github.com/Duelion/homebox-companion.git
cd homebox-companion
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
- **iOS Compatibility:** QR scanning now fully supports iOS devices including iPhone photo library

---

## 📝 Known Issues

None at this time. Please report issues at: https://github.com/Duelion/homebox-companion/issues

