"""Switch entities for MAP5000 points (Sperren) and outputs (Ein/Aus + Sperren)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_INFO, DOMAIN
from .coordinator import Map5000Coordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Map5000Coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    entities: list = []

    for p in data.get("points", []):
        if p.get("@self"):
            entities.append(Map5000PointSperren(coordinator, p))

    for o in data.get("outputs", []):
        if o.get("@self"):
            entities.append(Map5000OutputOn(coordinator, o))
            entities.append(Map5000OutputSperren(coordinator, o))

    async_add_entities(entities)


def _slug(siid: str) -> str:
    return siid.replace(".", "_").replace("/", "_").strip("_")


# ── Points ────────────────────────────────────────────────────────────────────

class Map5000PointSperren(CoordinatorEntity, SwitchEntity):
    """Switch ON = Melder gesperrt (bypassed), OFF = Melder aktiv."""

    _attr_icon = "mdi:shield-lock"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: Map5000Coordinator, point_data: dict) -> None:
        super().__init__(coordinator)
        self._siid: str = point_data["@self"].lstrip("/")
        name = point_data.get("name") or self._siid
        self._attr_name = f"{name} (Gesperrt)"
        self._attr_unique_id = f"map5000_point_sperren_{_slug(self._siid)}"

    @property
    def _point(self) -> dict | None:
        return next(
            (p for p in (self.coordinator.data or {}).get("points", [])
             if p.get("@self", "").lstrip("/") == self._siid),
            None,
        )

    @property
    def is_on(self) -> bool | None:
        p = self._point
        return bool(p.get("sperren")) if p is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        """Sperren (bypass) the detector."""
        await self.coordinator.async_send_cmd("point", self._siid, "DISABLE")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Entsperren (re-activate) the detector."""
        await self.coordinator.async_send_cmd("point", self._siid, "ENABLE")
        await self.coordinator.async_request_refresh()


# ── Outputs ───────────────────────────────────────────────────────────────────

class Map5000OutputOn(CoordinatorEntity, SwitchEntity):
    """Switch ON = output energised (EIN), OFF = output off (AUS)."""

    _attr_icon = "mdi:toggle-switch"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: Map5000Coordinator, output_data: dict) -> None:
        super().__init__(coordinator)
        self._siid: str = output_data["@self"].lstrip("/")
        name = output_data.get("name") or self._siid
        self._attr_name = name
        self._attr_unique_id = f"map5000_output_on_{_slug(self._siid)}"

    @property
    def _output(self) -> dict | None:
        return next(
            (o for o in (self.coordinator.data or {}).get("outputs", [])
             if o.get("@self", "").lstrip("/") == self._siid),
            None,
        )

    @property
    def is_on(self) -> bool | None:
        o = self._output
        return bool(o.get("on")) if o is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_cmd("output", self._siid, "ON")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send_cmd("output", self._siid, "OFF")
        await self.coordinator.async_request_refresh()


class Map5000OutputSperren(CoordinatorEntity, SwitchEntity):
    """Switch ON = output active (enabled), OFF = output gesperrt (disabled)."""

    _attr_icon = "mdi:shield-lock"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: Map5000Coordinator, output_data: dict) -> None:
        super().__init__(coordinator)
        self._siid: str = output_data["@self"].lstrip("/")
        name = output_data.get("name") or self._siid
        self._attr_name = f"{name} (Aktiv)"
        self._attr_unique_id = f"map5000_output_sperren_{_slug(self._siid)}"

    @property
    def _output(self) -> dict | None:
        return next(
            (o for o in (self.coordinator.data or {}).get("outputs", [])
             if o.get("@self", "").lstrip("/") == self._siid),
            None,
        )

    @property
    def is_on(self) -> bool | None:
        """ON = Aktiv (not gesperrt), OFF = Gesperrt."""
        o = self._output
        return (not bool(o.get("sperren", False))) if o is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        """Aktivieren = ENABLE."""
        await self.coordinator.async_send_cmd("output", self._siid, "ENABLE")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Sperren = DISABLE."""
        await self.coordinator.async_send_cmd("output", self._siid, "DISABLE")
        await self.coordinator.async_request_refresh()
