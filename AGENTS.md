# Agent Guidelines

Instructions for AI/LLM agents working on this codebase.

> **For user documentation**: See [README.md](README.md)

---

## Overview

**Homebox Companion** is an AI-powered companion app for [Homebox](https://github.com/sysadminsmedia/homebox) inventory management. Users take photos of items, and AI vision models automatically identify and catalog them.

---

## Development Commands

```bash
# Python (use uv, not pip)
uv sync                  # Install dependencies
uv add <package>         # Add dependency
uv run <command>         # Run in virtual env

# Linting & Type Checking
uv run ruff check .
uv run ty check
uv run vulture --min-confidence 70 --sort-by-size

# Testing
uv run pytest                 # Unit tests
uv run pytest -m integration  # Integration tests
uv run pytest -m live         # Live tests (real services)

# Frontend (in frontend/ directory)
npm install
npm run dev
npm run check            # TypeScript/Svelte validation
npm run lint             # ESLint (Svelte + Tailwind)
npm run lint:fix         # ESLint with auto-fix
npm run format:check     # Prettier format check
npm run format           # Prettier auto-format
```

---

## Build & Run Full App

Build the frontend and run the server locally:

```powershell
# 1. Build frontend (from frontend/ directory)
cd frontend
npm install
npm run build

# 2. Copy build to server static files
Remove-Item -Recurse -Force ../server/static/*
Copy-Item -Recurse -Force build/* ../server/static/

# 3. Run the server (from project root)
cd ..
uv run python -m server.app
```

The app will be available at `http://localhost:8000`.

---

## Environment Variables

```bash
HBC_LLM_API_KEY=sk-your-key             # Required
HBC_LLM_MODEL=gpt-5-mini                # Optional (default)
HBC_LLM_API_BASE=https://...            # Optional, for proxies
HBC_HOMEBOX_URL=https://demo.homebox.software
```

Demo credentials: `demo@example.com` / `demo`

---

## LLM Policy

- Uses **LiteLLM** for multi-provider support
- **Officially supported**: `gpt-5-mini`, `gpt-5-nano` only
- Other models: `HBC_LLM_ALLOW_UNSAFE_MODELS=true` (unsupported)
- Don't suggest alternative models in error messages

---

## Architecture Principles

- **Frontend**: SvelteKit + Svelte 5 runes, thin page views delegating to workflow services
- **Backend**: FastAPI with dependency injection, routes in `server/api/`
- **Package**: `src/homebox_companion/` for reusable Python library code
- **AI Prompts**: Modular builders in `ai/prompts.py`, user customizations **replace** defaults

### Key Patterns

- **Workflow services** (`lib/workflows/`): Single source of truth for scan flow state
- **VisionContext**: Shared dependency for all vision endpoints
- **Field Preferences**: Three-layer override (hardcoded → env vars → config file)
- **Item creation**: Two-step POST (create) → PUT (extended fields) due to Homebox API

### Frontend Design System

Design tokens are defined in `tailwind.config.js`. **Always use tokens instead of raw values** to maintain consistency.

| Category | ✅ Use This | ❌ Avoid |
|----------|-------------|----------|
| **Overlays** | `bg-neutral-950/60` | `bg-black/60` |
| **Text on dark** | `text-neutral-100`, `text-neutral-300` | `text-white`, `text-white/80` |
| **Semantic colors** | `warning-*`, `success-*`, `error-*` | `amber-*`, `yellow-*`, `red-*` |
| **Accent color** | `text-accent`, `text-primary-400` | `text-cyan-400`, `text-blue-400` |
| **Typography** | `text-body-sm`, `text-caption` | `text-sm`, `text-xs` |
| **Touch targets** | `min-h-touch`, `min-w-touch` | `min-h-[44px]`, `min-w-[44px]` |

**Canvas operations**: Use `CANVAS_COLORS` from `lib/utils/canvas-colors.ts` (synced with Tailwind tokens).

**CSS custom values**: In component `<style>` blocks, use `theme('colors.primary.500')` instead of hard-coded hex values.

---

## Pre-Commit Checklist

1. `uv run ruff check .`
2. `uv run ty check`
3. `uv run vulture --min-confidence 70 --sort-by-size`
4. `npm run check`
5. `cd frontend`
6. `npm run lint`
7. `npm run format:check`

---

## Common Pitfalls

- **Frontend**: Don't modify workflow state directly; use service methods
- **Frontend**: Use design system tokens (see table above), not raw Tailwind colors
- **Backend**: Extended fields (manufacturer, model, serial) require PUT after create
- **AI**: Customizations replace defaults—don't concatenate instructions

