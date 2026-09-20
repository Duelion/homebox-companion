# Homebox and Companion tests

The default pytest command runs fast unit and integration tests and excludes tests
marked `live`:

```powershell
uv sync --locked
uv run --no-sync pytest
```

The shared Homebox business and authentication suites use disposable Docker
servers and isolated accounts. No operator-provided Homebox credentials or paid
LLM account is required:

```powershell
uv run pytest -m live `
  tests/test_homebox_client.py `
  tests/test_homebox_auth_live.py `
  tests/test_homebox_upstream_live.py `
  tests/test_companion_auth_live.py `
  tests/test_label_print_live.py `
  tests/test_mcp_tools.py
```

The Companion live tests use a sentinel LLM key and exercise the Homebox boundary
without making an LLM request. Docker must be available on `PATH` with its daemon
running. A local run skips when Docker is unavailable; CI treats that as a failure.
Failures after Docker starts, including bootstrap or API-key provisioning failures,
fail the run.

The Homebox fixtures provide one authentication matrix:

- `homebox_auth_mode` runs shared business tests as `credentials` and `api_key`,
  with readable pytest IDs.
- `homebox_auth` provisions the selected credential through a setup-only client.
  API-key setup creates a real two-hour Homebox key and revokes it during teardown;
  secrets are excluded from fixture representations.
- `homebox_client` creates a fresh async transport per test. Its request hook
  requires bearer authentication and rejects cookies, so a login cookie cannot mask
  the credential under test. Do not call `login()` on it.
- `cleanup_items` and `cleanup_locations` accept IDs with `.append(id)` and remove
  them before authentication teardown. A test that deliberately revokes its
  credential must clean up first or use independent control credentials.

Use `-k api_key` or `-k credentials` for a focused matrix run. Legacy login,
refresh, and logout tests use `homebox_api_url` and `homebox_credentials` directly.
API-key-only classes can override `homebox_auth_mode`; see `TestAPIKeyLifecycle` in
`test_homebox_auth_live.py`.

The browser auth and failed-item recovery suites use mocked API responses and a
local SvelteKit preview; they do not call Homebox or an LLM. From `frontend/`,
install dependencies and run:

```powershell
npm ci
npx playwright install chrome   # required when the Chrome channel is absent
npm run test:browser
```

`frontend/playwright.config.ts` builds the frontend and starts its preview server
on `127.0.0.1:4173`. Local runs select the installed Google Chrome channel. CI
selects bundled Chromium and installs it with
`npx playwright install --with-deps chromium`. To use bundled Chromium locally,
install it and set `CI=true` for the test command.

The validation workflow runs on pull requests and `dev` pushes. Python checks use
the committed `uv.lock`; frontend checks use `npm ci`. Docker-backed Homebox tests
run in a separate bounded job with a sentinel LLM key and the explicit six-file
allowlist above. Do not broaden that job to all live tests: other live tests may
require a real LLM account.

CI runs `ty check --exit-zero-on-warning` to preserve the project's existing
warning-level diagnostics as informational output. Type errors still fail the
job. The recovery baseline currently has 51 warnings, primarily stale suppression
comments and existing MCP typing diagnostics; this is not a warning-free result.
