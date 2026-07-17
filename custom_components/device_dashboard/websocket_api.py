"""WebSocket API for the Per-Device Default Dashboard integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_MAPPINGS,
    CONF_USERS,
    DEFAULT_KEY,
    DOMAIN,
)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Register the websocket command."""
    websocket_api.async_register_command(hass, websocket_get_config)


@websocket_api.websocket_command(
    {vol.Required("type"): "device_dashboard/get_config"}
)
@callback
def websocket_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the dashboard mapping for the current user.

    Resolves the per-user override from ``connection.user.id``, falling back to the
    global ``__default__`` entry. Reads ``entry.options`` live, so option changes take
    effect on the next call with no reload. Only non-sensitive dashboard url_paths are
    exposed.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_result(msg["id"], {CONF_MAPPINGS: {}})
        return

    users = entries[0].options.get(CONF_USERS, {})
    cfg = users.get(connection.user.id) or users.get(DEFAULT_KEY, {})
    mappings = cfg.get(CONF_MAPPINGS, {})

    # Drop any target that's no longer a live dashboard, so the module never redirects to a
    # deleted one. "lovelace" (the built-in overview) is always allowed: it's keyed None in
    # the collection, so it isn't in the url_path set. A user-made dashboard actually named
    # "home" is still allowed via that set. Use `is not None` so an empty collection still
    # filters — a truthiness check would skip filtering and let stale targets through.
    dashboards = getattr(hass.data.get("lovelace"), "dashboards", None)
    if dashboards is not None:
        valid = {url_path for url_path in dashboards if url_path} | {"lovelace"}
        mappings = {cls: target for cls, target in mappings.items() if target in valid}

    connection.send_result(msg["id"], {CONF_MAPPINGS: mappings})
