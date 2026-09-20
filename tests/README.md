# Homebox and Companion tests

The default pytest command runs fast unit and integration tests and excludes tests
marked `live`:

```powershell
uv run pytest
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

The browser auth suite uses mocked API responses and a local SvelteKit preview; it
does not call Homebox or an LLM. From `frontend/`, install dependencies and run:

```powershell
npm install
npx playwright install chrome   # required when the Chrome channel is absent
npm run test:browser
```

`frontend/playwright.config.ts` selects the installed Google Chrome channel, builds
the frontend, starts its preview server on `127.0.0.1:4173`, and runs
`frontend/tests/browser/auth.spec.ts`. A system Chrome installation that the
Playwright `chrome` channel can launch is required; bundled Chromium alone is not
sufficient for this configuration.
