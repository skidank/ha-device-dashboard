# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant **custom integration** (domain `device_dashboard`, packaged for HACS)
that opens a different default dashboard per device type for the same user — e.g. iOS app
→ `Home Mobile`, desktop browser → `Home Desktop`.

## Commands

There is no test suite or build step. Validation is static + CI:

```sh
# Static checks (run these after any change)
python3 -m py_compile custom_components/device_dashboard/*.py
python3 -m json.tool custom_components/device_dashboard/manifest.json > /dev/null   # + strings.json, translations/en.json, hacs.json
node --check custom_components/device_dashboard/frontend/router.js
```

`py_compile` only checks syntax (it does not import `homeassistant`, which is not a repo
dependency). Full validation — **hassfest** + **HACS Action** — runs in CI
(`.github/workflows/validate.yml`) on push/PR and on a daily schedule; there is no way to
run those meaningfully without the GitHub environment.

## Architecture: server registers, browser decides

The "which dashboard loads by default" decision is `defaultPanel`, a **per-user** setting
applied **client-side** by the frontend — there is no per-request server hook and the SPA
only requests the base URL once. So device-type detection can only happen in the browser
(reading `navigator.userAgent`). The split follows from that:

- **`frontend/router.js`** is where the actual routing decision lives. Injected on every
  page via `add_extra_js_url`, it classifies the UA, calls the websocket command for the
  mapping, and redirects with a **full navigation** (`location.replace`) so the target
  dashboard loads fresh — load-time frontend plugins (e.g. kiosk-mode) then initialize on it.
- **The Python package only plumbs**: serves the JS as a static path, registers it, exposes
  the mapping over a websocket command, and provides the config/options UI. It contains no
  routing logic.

Launch flow: app boots → frontend's own `defaultPanel` navigation → `router.js` classifies
→ `device_dashboard/get_config` returns this user's mapping → redirect (only from a landing
path, only once per launch).

## Cross-file invariants (do not break these)

- **No options reload.** The websocket command reads `entry.options` live and `router.js`
  only fetches config at launch, so an options change already applies on the next launch.
  Do **not** add an update listener / `async_reload` — `async_setup_entry` re-registering
  the same static path crashes (aiohttp rejects a duplicate resource). The global
  frontend/http registration is one-time, guarded by the `FRONTEND_REGISTERED` flag in
  `hass.data`.
- **Singleton via manifest.** `"single_config_entry": true` makes HA block a second config
  entry; the config flow has no manual guard, and code assumes exactly one entry
  (`async_entries(DOMAIN)[0]`).
- **Options shape:** `options["users"][<key>] = {"mappings": {...}}` where `<key>` is an HA
  **auth `user.id`** or the literal `"__default__"`. The WS command resolves the user's
  override **or** `__default__` (never merged) and returns only `mappings`. router.js derives
  the launch page itself from `hass.userData.default_panel`, so there's no cached landing
  state that can go stale.
- **"Unset" is the `__none__` sentinel**, not an absent field — HA dropdowns can't be
  cleared once set. Saving drops `__none__` values and removes a user key entirely if it
  becomes empty.
- **`router.js` runs once per full page load** (it's a `type=module` script; SPA navigation
  never re-runs it). That, not the `window.__deviceDashboardRouted` backstop, is what
  prevents bouncing the user after manual navigation. The `settle()` step waits for the
  path (and the user's default panel) to resolve before it decides, so a real dashboard
  renders before the redirect rather than reloading straight from the loading splash. The redirect itself is a
  full navigation (`location.replace`), so there's no soft-nav race to lose and load-time
  frontend plugins initialize on the target dashboard.
  The redirect only fires from a *landing* page — `""`, `lovelace`, `home`, or the user's
  default panel (`hass.userData?.default_panel`, resolved as the frontend does) — so a launch
  redirects but a deep link to another dashboard doesn't. `target` is validated as a slug and
  resolved same-origin before navigating (no protocol-relative off-origin redirect).

## Home Assistant API notes

- `hass.data["lovelace"].dashboards` is `dict[str | None, LovelaceConfig]` keyed by
  `url_path` (`None` = default). Access `.dashboards` by **dot notation** (bracket
  sub-access was deprecated, removed 2026.2). `dashboard.config` is the dashboard
  **metadata** dict (title/icon/url_path) — a synchronous read; the card config is separate
  and async. Verified against HA core 2026.7.2.
- The integration depends on **undocumented frontend internals** (`<home-assistant>`
  element, `hass.connection`, `hass.userData.default_panel`). A frontend release can break
  `router.js` silently — re-run the behavioral/detection tests on each HA/frontend bump.
- **The module can't be un-injected**: the frontend has no API to remove an `extra_js_url`,
  so removing the integration requires an HA restart to stop serving `router.js`.

## Deploying to Home Assistant

Treat any target instance as production: run the static checks (and ideally a dev-instance
test) before deploying, and don't copy into a live config or restart HA without confirming
first. The module can't be un-injected (see above), so a full removal needs an HA restart.

Repo: `github.com/skidank/ha-device-dashboard`.
