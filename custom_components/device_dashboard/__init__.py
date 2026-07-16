"""Per-Device Default Dashboard integration.

Serves a small ES module into the frontend that, on launch, classifies the client by
User-Agent and redirects to a per-device-class dashboard. This package only serves the
module, registers a websocket command that hands it the mapping, and provides the
config/options UI — the routing decision itself happens in frontend/router.js.
"""

from __future__ import annotations

import os

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import websocket_api
from .const import FRONTEND_REGISTERED, MODULE_URL


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Per-Device Default Dashboard from its (single) config entry."""
    # One-time global frontend/http registration. These are NOT per-entry: the same
    # static path can only be registered once (aiohttp rejects a duplicate resource),
    # so guard against a re-setup re-running them. An options change needs no reload —
    # the websocket command reads entry.options live and router.js only fetches config
    # at launch.
    if not hass.data.get(FRONTEND_REGISTERED):
        js_path = os.path.join(os.path.dirname(__file__), "frontend", "router.js")
        await hass.http.async_register_static_paths(
            [StaticPathConfig(MODULE_URL, js_path, cache_headers=False)]
        )
        add_extra_js_url(hass, MODULE_URL)  # inject as an ES module on every page
        websocket_api.async_setup(hass)  # register device_dashboard/get_config
        hass.data[FRONTEND_REGISTERED] = True

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry.

    The frontend exposes no public API to remove an extra_js_url or a registered static
    path, so the module keeps being served until Home Assistant restarts (a known
    frontend limitation, shared with browser_mod — see README). Unload therefore has
    nothing to tear down and simply succeeds.
    """
    return True
