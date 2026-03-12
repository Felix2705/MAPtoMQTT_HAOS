"""Config flow for MAP5000 integration."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN


class Map5000ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup dialog."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict = {}

        if user_input is not None:
            url = user_input[CONF_BASE_URL].rstrip("/")
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(
                    f"{url}/api/status",
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 200:
                        await self.async_set_unique_id("map5000")
                        self._abort_if_unique_id_configured(
                            updates={CONF_BASE_URL: url}
                        )
                        return self.async_create_entry(
                            title="MAP5000",
                            data={CONF_BASE_URL: url},
                        )
                    errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str}
            ),
            errors=errors,
            description_placeholders={
                "default_url": DEFAULT_BASE_URL,
            },
        )
