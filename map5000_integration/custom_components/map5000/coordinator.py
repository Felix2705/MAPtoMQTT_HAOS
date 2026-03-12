"""DataUpdateCoordinator for MAP5000 – polls the addon REST API."""
from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

logger = logging.getLogger(__name__)


class Map5000Coordinator(DataUpdateCoordinator):
    """Polls GET /api/status from the MAP to MQTT addon."""

    def __init__(self, hass: HomeAssistant, base_url: str) -> None:
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self._base_url = base_url.rstrip("/")
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict:
        try:
            async with self._session.get(
                f"{self._base_url}/api/status",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status}")
                data: dict = await resp.json()
        except aiohttp.ClientError as exc:
            raise UpdateFailed(f"Cannot reach MAP5000 addon: {exc}") from exc

        if not data.get("map_online", True):
            raise UpdateFailed("MAP5000 controller is offline")

        return data

    async def async_send_cmd(self, resource: str, siid: str, cmd: str) -> dict:
        """Send a command to the MAP via POST /api/cmd."""
        async with self._session.post(
            f"{self._base_url}/api/cmd",
            json={"resource": resource, "siid": siid, "cmd": cmd},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            result: dict = await resp.json()
        if not result.get("ok"):
            logger.error("MAP command failed: %s %s %s → %s", resource, siid, cmd, result)
        return result
