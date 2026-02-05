"""The Safetec Water integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, DOMAIN

PLATFORMS: list[str] = ["sensor"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Safetec Water from YAML."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Safetec Water from a config entry."""
    host = entry.options.get(CONF_HOST, entry.data.get(CONF_HOST))
    if not host:
        _LOGGER.error("Safetec Water config entry missing host; aborting setup")
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CONF_HOST: host,
        CONF_PORT: entry.options.get(CONF_PORT, entry.data.get(CONF_PORT, DEFAULT_PORT)),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Safetec Water config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
