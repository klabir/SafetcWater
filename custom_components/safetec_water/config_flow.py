"""Config flow for Safetec Water."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN


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
