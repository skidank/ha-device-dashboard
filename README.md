# Per-Device Default Dashboard

A Home Assistant custom integration that opens a **different default dashboard per
device type** for the same user — e.g. `Home Mobile` in the iOS/Android companion app and
`Home Desktop` in a desktop browser — configurable from the UI, with no automations and no
per-browser registration.

Home Assistant's default dashboard (`defaultPanel`) is a **per-user** setting applied by
the frontend; there is no native way to vary it by device. This integration serves a small
ES module into the frontend that, on launch, classifies the client by User-Agent and
redirects to the mapped dashboard.

## How it works

- On every page it injects `router.js` (via `frontend.add_extra_js_url`).
- At launch the module classifies the client (`ios_app` / `android_app` / `mobile_web` /
  `desktop`), fetches the mapping over a websocket command (`device_dashboard/get_config`),
  and — only from a launch/landing page, once per launch — redirects with a full
  navigation (`location.replace`) so the target dashboard loads fresh.
- Mappings are **per-user** with a global **default** fallback, edited from the UI.

Deep links (e.g. a notification opening a specific view) and manual navigation are left
alone, so you won't get "bounced" back.

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/skidank/ha-device-dashboard`, category **Integration**.
2. Install **Per-Device Default Dashboard**, then restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Per-Device Default Dashboard**.

## Configuration

Open **Configure** on the integration and use the menu:

- **Edit default (all users)** — the mapping applied to everyone without an override.
- **Edit a user override** — pick an HA user, then set their mapping.
- **Remove a user override** — delete a user's override (they fall back to the default).

For each device type, pick a dashboard or leave it as **“(no override — use default)”** —
an unset class does nothing, respecting the user's normal default.

### Device classification

| Class         | Matched when the User-Agent…                     |
|---------------|--------------------------------------------------|
| `ios_app`     | contains `io.robbie.HomeAssistant` (incl. iPad app) |
| `android_app` | contains `io.homeassistant.companion.android`    |
| `mobile_web`  | looks like a phone/tablet browser (not the app)  |
| `desktop`     | anything else (fallback)                          |

> iPadOS Safari masquerades as macOS, so the iPad **browser** classifies as `desktop`; the
> iPad **app** classifies as `ios_app`.

## Known limitations

- **Launch flash.** Because the decision happens client-side, the launch briefly renders
  the frontend's default panel before swapping to the mapped dashboard. This is inherent to
  any client-side approach.
- **Removal needs a restart.** The frontend has no public API to un-inject a module, so
  after removing the integration the module keeps being served until Home Assistant
  restarts (a known frontend limitation, shared with browser_mod).
- **Map only to dashboards the user can access**, or the frontend will show its normal
  "not found/allowed" page.
- Relies on frontend internals (the `<home-assistant>` element and the `hass` object);
  a frontend release could change these — the CI checks re-run on schedule.

## Development / validation

```sh
python -m py_compile custom_components/device_dashboard/*.py
python -m json.tool custom_components/device_dashboard/manifest.json > /dev/null
```

CI (`.github/workflows/validate.yml`) runs **hassfest** and the **HACS Action**.

## License

MIT — see [LICENSE](LICENSE).
