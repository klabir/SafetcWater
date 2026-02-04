"""Config flow for Safetec Water."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN


class SafetecWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Safetec Water."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, str] | None = None):
        """Handle the initial step."""
        if user_input is None:
            return self._show_form()

        await self.async_set_unique_id(user_input[CONF_HOST])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    def _show_form(self):
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SafetecWaterOptionsFlow(config_entry)


class SafetecWaterOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Safetec Water."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, int] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options
        data = self._config_entry.data
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HOST,
                    default=options.get(CONF_HOST, data.get(CONF_HOST, "")),
                ): str,
                vol.Optional(
                    CONF_PORT,
                    default=options.get(CONF_PORT, data.get(CONF_PORT, DEFAULT_PORT)),
                ): int,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
