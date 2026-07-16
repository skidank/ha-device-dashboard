"""Constants for the Per-Device Default Dashboard integration."""

from __future__ import annotations

DOMAIN = "device_dashboard"

# URL the injected ES module is served at.
MODULE_URL = "/device_dashboard_static/router.js"

# hass.data flag marking that the one-time global frontend/http registration ran.
FRONTEND_REGISTERED = f"{DOMAIN}_frontend"

# Options keys.
CONF_USERS = "users"
CONF_MAPPINGS = "mappings"
CONF_LANDING_PATHS = "landing_paths"

# Key under CONF_USERS for the global default (applies to users without an override).
DEFAULT_KEY = "__default__"

# Sentinel selector value meaning "no override for this device class".
NONE_VALUE = "__none__"

# Device classes. Order matters for classification (see router.js) and display.
CLASS_IOS_APP = "ios_app"
CLASS_ANDROID_APP = "android_app"
CLASS_MOBILE_WEB = "mobile_web"
CLASS_DESKTOP = "desktop"

DEVICE_CLASSES: tuple[str, ...] = (
    CLASS_IOS_APP,
    CLASS_ANDROID_APP,
    CLASS_MOBILE_WEB,
    CLASS_DESKTOP,
)
