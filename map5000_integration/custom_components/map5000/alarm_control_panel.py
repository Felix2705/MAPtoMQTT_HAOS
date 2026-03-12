"""Alarm control panel entities – one per MAP5000 area."""
from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
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
    areas = (coordinator.data or {}).get("areas", [])
    async_add_entities(
        Map5000Area(coordinator, a) for a in areas if a.get("@self")
    )


def _slug(siid: str) -> str:
    return siid.replace(".", "_").replace("/", "_").strip("_")


class Map5000Area(CoordinatorEntity, AlarmControlPanelEntity):
    """Represents one MAP5000 area (Bereich)."""

    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_NIGHT
    )
    _attr_code_arm_required = False
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: Map5000Coordinator, area_data: dict) -> None:
        super().__init__(coordinator)
        self._siid: str = area_data["@self"].lstrip("/")
        name = area_data.get("name") or self._siid
        self._attr_name = name
        self._attr_unique_id = f"map5000_area_{_slug(self._siid)}"

    @property
    def _area(self) -> dict | None:
        return next(
            (a for a in (self.coordinator.data or {}).get("areas", [])
             if a.get("@self", "").lstrip("/") == self._siid),
            None,
        )

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        a = self._area
        if a is None:
            return None
        return (
            AlarmControlPanelState.ARMED_AWAY
            if a.get("armed")
            else AlarmControlPanelState.DISARMED
        )

    @property
    def extra_state_attributes(self) -> dict:
        a = self._area
        if not a:
            return {}
        return {k: v for k, v in a.items() if k not in ("@self", "name")}

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self.coordinator.async_send_cmd("area", self._siid, "ARM")
        await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        await self.coordinator.async_send_cmd("area", self._siid, "ARM")
        await self.coordinator.async_request_refresh()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        await self.coordinator.async_send_cmd("area", self._siid, "ARM")
        await self.coordinator.async_request_refresh()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self.coordinator.async_send_cmd("area", self._siid, "DISARM")
        await self.coordinator.async_request_refresh()

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Reset / acknowledge alarms."""
        await self.coordinator.async_send_cmd("area", self._siid, "RESET")
        await self.coordinator.async_request_refresh()
