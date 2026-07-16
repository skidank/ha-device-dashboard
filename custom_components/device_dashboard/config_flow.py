"""Config and options flow for Per-Device Default Dashboard."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_MAPPINGS,
    CONF_USERS,
    DEFAULT_KEY,
    DEVICE_CLASSES,
    DOMAIN,
    NONE_VALUE,
)

TITLE = "Per-Device Default Dashboard"


class DeviceDashboardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial (singleton) config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single config entry (``single_config_entry`` blocks duplicates)."""
        if user_input is not None:
            return self.async_create_entry(title=TITLE, data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return DeviceDashboardOptionsFlow(config_entry)


class DeviceDashboardOptionsFlow(OptionsFlow):
    """Per-user dashboard mapping, with a global default fallback."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        # Stored under a private name so we never assign the deprecated
        # ``self.config_entry`` (works across HA versions).
        self._config_entry = config_entry
        self._edit_key: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Top-level menu: edit the default, edit a user, or remove a user override."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["edit_default", "edit_user", "remove_user"],
        )

    async def async_step_edit_default(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the global default mapping (applies to users without an override)."""
        self._edit_key = DEFAULT_KEY
        return await self.async_step_edit_mappings()

    async def async_step_edit_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick an HA auth user, then edit their mapping."""
        if user_input is not None:
            self._edit_key = user_input["user"]
            return await self.async_step_edit_mappings()

        users = await self.hass.auth.async_get_users()
        options = [
            SelectOptionDict(value=user.id, label=user.name or user.id)
            for user in users
            if user.is_active and not user.system_generated
        ]
        schema = vol.Schema(
            {
                vol.Required("user"): SelectSelector(
                    SelectSelectorConfig(
                        options=options, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="edit_user", data_schema=schema)

    async def async_step_remove_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a per-user override."""
        users = dict(self._config_entry.options.get(CONF_USERS, {}))
        removable = [key for key in users if key != DEFAULT_KEY]
        if not removable:
            return self.async_abort(reason="no_user_overrides")

        if user_input is not None:
            users.pop(user_input["user"], None)
            return self._save_users(users)

        names = {
            user.id: (user.name or user.id)
            for user in await self.hass.auth.async_get_users()
        }
        options = [
            SelectOptionDict(value=key, label=names.get(key, key)) for key in removable
        ]
        schema = vol.Schema(
            {
                vol.Required("user"): SelectSelector(
                    SelectSelectorConfig(
                        options=options, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="remove_user", data_schema=schema)

    async def async_step_edit_mappings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Per-device-class dashboard dropdowns for the chosen key."""
        if user_input is not None:
            return self._save_mappings(user_input)

        users = self._config_entry.options.get(CONF_USERS, {})
        existing = users.get(self._edit_key, {}).get(CONF_MAPPINGS, {})
        selector = SelectSelector(
            SelectSelectorConfig(
                options=self._dashboard_options(), mode=SelectSelectorMode.DROPDOWN
            )
        )
        schema = vol.Schema(
            {
                vol.Optional(
                    device_class,
                    description={
                        "suggested_value": existing.get(device_class, NONE_VALUE)
                    },
                ): selector
                for device_class in DEVICE_CLASSES
            }
        )
        return self.async_show_form(step_id="edit_mappings", data_schema=schema)

    # --- helpers -------------------------------------------------------------

    def _dashboard_options(self) -> list[SelectOptionDict]:
        """Build dropdown options from the Lovelace dashboards collection.

        ``.config`` is the dashboard *metadata* dict (title/icon/mode/url_path), set once
        in ``LovelaceConfig.__init__`` and never reassigned, so reading the title is a
        plain synchronous lookup that does not trigger a config load. It is ``None`` only
        for the None-key default dashboard, which we skip.
        """
        options = [
            SelectOptionDict(value=NONE_VALUE, label="(no override — use default)"),
            SelectOptionDict(value="lovelace", label="Overview (default)"),
        ]
        lovelace = self.hass.data.get("lovelace")
        dashboards = getattr(lovelace, "dashboards", {}) if lovelace else {}
        for url_path, dashboard in dashboards.items():
            if url_path and getattr(dashboard, "config", None):
                title = dashboard.config.get("title", url_path)
                options.append(
                    SelectOptionDict(value=url_path, label=f"{title} ({url_path})")
                )
        return options

    def _save_mappings(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        mappings = {
            device_class: value
            for device_class, value in user_input.items()
            if value and value != NONE_VALUE
        }
        users = dict(self._config_entry.options.get(CONF_USERS, {}))
        if mappings:
            # Store mappings only. router.js recognizes the launch page from the live
            # default panel (hass.userData.default_panel), so there's no landing list to
            # derive/cache here — which would otherwise go stale when the default changes.
            users[self._edit_key] = {CONF_MAPPINGS: mappings}
        else:
            # No mappings selected → drop the key entirely (falls back to default).
            users.pop(self._edit_key, None)
        return self._save_users(users)

    def _save_users(self, users: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(title="", data={CONF_USERS: users})
