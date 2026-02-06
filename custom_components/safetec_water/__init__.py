"""The Safetec Water integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

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

    port = hass.data[DOMAIN][entry.entry_id][CONF_PORT]
    session = aiohttp_client.async_get_clientsession(hass)
    test_url = f"http://{host}:{port}/trio/get/vol"
    try:
        async with session.get(test_url, timeout=10) as response:
            response.raise_for_status()
            await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Safetec Water device at {host}:{port}: {err}"
        ) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Safetec Water config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
