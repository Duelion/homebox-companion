# Frontend architecture

The frontend is a SvelteKit app using Svelte 5 runes and Tailwind CSS 4. Pages
coordinate user interaction and delegate durable workflow state and operations
to services. This guide records conventions visible in the current code; it is
intended for contributors changing the frontend.

## Workflow state and ownership

`scanWorkflow` coordinates capture, analysis, review, submission, and
persistence. Its `state` getter exposes a stable frozen view with recursively
readonly types. Components should derive values from that view and make changes
through workflow methods, rather than mutating values from the view. Phase
services own their respective state and operations; for example,
`CaptureService` manages captured images and `ReviewService` manages detected
and confirmed items.

`ScanWorkflow` persists workflow state to IndexedDB through `ScanPersistence`.
Ordinary state changes schedule a debounced save; transient phases such as
analysis and submission are skipped. Critical transitions use explicit
awaited persistence where needed because the `beforeunload` flush is best
effort. Saves snapshot image metadata and item fields together before asynchronous
conversion; superseded saves cannot overwrite a newer revision. During recovery,
`ScanPersistence` creates runtime image URLs while
deserializing. It transfers them to workflow state only after the full draft
is valid and the request context is still current; partial or stale recovery
revokes every URL it created.

Captured image object URLs are resources owned by the capture workflow: removal
and clear operations revoke URLs for removed images. A component that creates
temporary URLs for its own display owns a separate `createObjectUrlManager`
and calls its cleanup on destroy. Revoke each URL through its owner; do not
revoke a URL still used by workflow state. `locationNavigator.saveLocation`
owns location refresh and cache updates after a save; when the selected
location is edited, it updates the selected location in `scanWorkflow` through
`setLocation`.

The review page copies the selected workflow item into a local editable draft.
Its effect resets the draft when the current item changes, and invalidates
pending `ReviewEditor` work at that boundary. The editor also invalidates work
when the page is destroyed. Async editor results must be guarded by the
editor's current-operation state so an older response cannot overwrite a newer
draft.

## Svelte state and effects

Use `$derived` for values that stay coupled to props or shared state, such as
page values derived from `workflow.state`. If a prop-backed value needs a
local override, use a writable derived value so it follows new props until the
user changes it; after reassignment, it keeps that override until a dependency
changes, at which point it derives again. Use independent `$state` for genuine
drafts or UI state with its own lifecycle. When reopening an editor or changing
the identity that defines a draft, reset it explicitly in an effect or handler,
as the review page does.

Effects that allocate resources return synchronous cleanup for timers,
animation frames, event listeners, requests, and observers. Clear timers
started by handlers on component teardown. Async mount work must check that
the component is still active before creating resources after an await.

## Authentication transport

`api/client.ts` owns request handling and automatic one-time retry after a
401. The token refresh service does not import the API client: the client
registers a refresh transport, while the service owns refresh scheduling,
visibility handling, and lifecycle integration with `authStore`. Keep this
dependency direction so refresh scheduling does not create an API-client
import cycle.

## Styling and design tokens

`frontend/src/app.css` is the Tailwind 4 theme and reusable utility source.
Prefer its semantic color, typography, spacing, touch-target, radius, and
shadow tokens to raw values. Component style blocks that use Tailwind
directives include a relative `@reference` to `app.css`; ordinary CSS can
refer to theme variables such as `var(--color-primary-500)`.

Define literal colors only in the central `@theme` color tokens. Derive alpha
colors and glows with `color-mix(in srgb, var(--color-…) …%, transparent)` so
palette changes propagate. `npm run lint:css` checks stylesheet and component
style declarations; inline runtime values and canvas colors have separate checks.

Use `@utility` for reusable helpers that need Tailwind variants. Keep component
recipes in `@layer components` and component-specific selectors scoped locally.
Cards share `card-surface`; `.card` adds compact section spacing and radius,
while `Card.svelte` explicitly selects its larger radius and padding variant.

Use `duration-fast` for the shared 150ms interaction timing. Other durations may
remain explicit when an animation or transition has distinct timing. Use semantic
typography for body copy and headings; standard scale sizes are permitted for
deliberate display elements such as numeric statistics and the brand wordmark.
Dynamic dimensions, progress, and per-item animation timing belong in inline
styles; static reusable styling belongs in a class.

Custom utilities such as `input`, `card`, `min-h-touch`, and `duration-fast`
are registered with `@utility`. Animation delay utilities such as
`animation-delay-100` set animation timing only; they do not set transition
delay. Radius utilities follow the theme values: for example `rounded-xs` is
2px, `rounded-sm` is 4px, and `rounded-pill` is 14px (the `--radius-pill`
token is 0.875rem).

Canvas drawing colors live in `frontend/src/lib/utils/canvas-colors.ts` and
mirror the CSS values used by canvas operations. The browser
`design-tokens.spec.ts` checks their synchronization with `app.css`; keep them
synchronized when changing the theme.

## Checks

`npm run lint` includes a local ESLint rule that flags discouraged utility
classes in Svelte markup and class-building expressions. Its rule behavior is
covered by `npm run test:unit`. The browser `styling-contracts.spec.ts` checks
computed utility behavior and captures diagnostic review screenshots. See
[tests/README.md](../tests/README.md) for commands and canonical Linux Chromium
visual snapshot guidance.
