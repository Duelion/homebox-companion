# Homebox and Companion tests

The default pytest command runs fast unit and integration tests and excludes tests
marked `live`:

```powershell
uv sync --locked
uv run --no-sync pytest
```

The development dependencies include HTTPX2, which Starlette automatically uses
as its `TestClient` backend. Install them with `uv sync --locked` before testing.

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

The browser suite uses mocked API responses and a local SvelteKit preview; it
does not call Homebox or an LLM. Use Node 26.10.0 to match frontend CI and the
Docker frontend builder. From `frontend/`, install dependencies, build
once, and run Playwright against that build:

```powershell
npm ci
npx playwright install --with-deps chromium webkit
npm run build
npm run test:browser:run
```

`frontend/playwright.config.ts` starts the preview server on
`127.0.0.1:4173` with a strict port and does not build. Its `browser-test` mode
disables Vite's backend proxy so late teardown requests cannot reach a real API.
`npm run test:browser`
is the convenience command that builds once and then runs the suite. The normal
project is bundled Chromium. Linux runs include `@visual` tests; the short
`@mobile` selection runs in mobile WebKit. `PLAYWRIGHT_SYSTEM_CHROME=1` opts into
an additional installed Chrome project for local debugging. CI installs both
browser engines, runs the build, then runs `test:browser:run`.

For the canonical screenshot platform on Windows or macOS, Docker can run the
same Linux/browser version used to create the baselines. From the repository
root in PowerShell, run this in one session (the named volume retains Linux
dependencies; source and build output remain in the checkout):

```powershell
$repo = (Get-Location).Path
docker run --rm --init --ipc=host `
  -v "${repo}:/work" `
  -v homebox-browser-node-modules:/work/frontend/node_modules `
  -w /work/frontend mcr.microsoft.com/playwright:v1.63.0-noble `
  bash -lc "npm ci && npm run build && npm run test:browser:run"
```

Run `npm run build` only once before `npm run test:browser:run`; the Playwright
web server serves that build. The container writes build output into the
checkout, so avoid a simultaneous host build. The named `node_modules` volume
keeps Linux dependencies separate from host dependencies. For subsequent runs
using the same volume, omit `npm ci` unless dependencies changed, and rebuild
only after frontend source changes.

The Playwright image supplies its own Node runtime. For a Node migration,
install the selected runtime into that environment and verify `node --version`
before running the checks; the canonical browser image alone does not validate
the application's selected Node version.

To debug a test, narrow by file/title and use the HTML report or retained trace:

```powershell
npx playwright test tests/browser/scan.spec.ts --grep "submits a corrected item"
npx playwright show-report
$trace = Get-ChildItem test-results -Recurse -Filter trace.zip | Select-Object -First 1
npx playwright show-trace $trace.FullName
```

Reports are written to `playwright-report/`; traces and failure screenshots go
under `test-results/`. The shared fixture releases request gates and reports
undeclared `/api/` calls, unexpected external requests, mock-handler errors, and
unhandled page errors at teardown. Allow a page error only inside the specific
test that deliberately exercises it (`api.allowPageError(...)`); investigate
unknown API calls by adding an explicit method/path handler or correcting the
request under test. Do not silence fixture diagnostics globally.

Shared setup lives in `tests/browser/fixtures/`. Extend `fixtures/api.ts` with
an explicit baseline only for stable startup behavior needed across workflows;
otherwise, add a test-specific `api.on(method, path, handler)` in the test or a
focused helper. Handlers are matched by HTTP method and path, with the latest
registration taking precedence, so an override stays local and explicit. Put
typed scenario builders in `fixtures/data.ts`; put reusable user actions in
`helpers/` while leaving the main action and outcome assertion readable in each
test. Add `@mobile` only to a small interaction case intended for the mobile
WebKit project. Add `@visual` only for an intentional Linux screenshot baseline.

The screenshot set has two visual tests and five PNG baselines. Update them only
on the canonical Linux Chromium project after reviewing the rendered change:

```powershell
npx playwright test presentation.spec.ts --project chromium --grep '@visual' --update-snapshots
git diff -- tests/browser
```

Do not update snapshots in a full-suite command or CI. Locally served font bytes
are pinned under `tests/browser/assets/fonts/`; their adjacent files preserve
the SIL Open Font License notices. Keep these files and source/version notes
together when refreshing typography so screenshots do not depend on network font
responses.

These browser tests establish UI behavior against declared mock responses. They
do not establish agreement with a running FastAPI/Homebox deployment or a real
LLM/provider, nor do mobile emulation and screenshot comparisons replace
real-device checks. Backend contract and live behavior remain covered by the
appropriate Python suites.

The validation workflow runs on pull requests and `dev` pushes. Python checks use
the committed `uv.lock`; frontend checks use `npm ci`. Docker-backed Homebox tests
run in a separate bounded job with a sentinel LLM key and the explicit six-file
allowlist above. Do not broaden that job to all live tests: other live tests may
require a real LLM account.

CI runs `ty check --error-on-warning` so both type errors and warnings fail the
job. Keep the type-check baseline free of diagnostics; validate dynamic inputs
at model boundaries and preserve each tool's parameter type in its interface.
