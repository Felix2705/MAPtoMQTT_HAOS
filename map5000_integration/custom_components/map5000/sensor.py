"""Sensor entities – status label per point + MAP connectivity sensor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
    points = (coordinator.data or {}).get("points", [])
    entities: list = [Map5000PointStatus(coordinator, p) for p in points if p.get("@self")]
    entities.append(Map5000ConnectivitySensor(coordinator))
    async_add_entities(entities)


def _slug(siid: str) -> str:
    return siid.replace(".", "_").replace("/", "_").strip("_")


class Map5000PointStatus(CoordinatorEntity, SensorEntity):
    """Shows Frei / Ausgelöst / Gesperrt for a MAP5000 detector."""

    _attr_icon = "mdi:shield-check"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: Map5000Coordinator, point_data: dict) -> None:
        super().__init__(coordinator)
        self._siid: str = point_data["@self"].lstrip("/")
        name = point_data.get("name") or self._siid
        self._attr_name = f"{name} (Status)"
        self._attr_unique_id = f"map5000_point_status_{_slug(self._siid)}"

    @property
    def _point(self) -> dict | None:
        return next(
            (p for p in (self.coordinator.data or {}).get("points", [])
             if p.get("@self", "").lstrip("/") == self._siid),
            None,
        )

    @property
    def native_value(self) -> str | None:
        p = self._point
        return p.get("status_label", "Unbekannt") if p is not None else None


class Map5000ConnectivitySensor(CoordinatorEntity, SensorEntity):
    """Shows whether the MAP5000 controller is reachable."""

    _attr_icon = "mdi:lan-connect"
    _attr_name = "MAP5000 Verbindung"
    _attr_unique_id = "map5000_connectivity"
    _attr_device_info = DEVICE_INFO

    @property
    def native_value(self) -> str:
        if self.coordinator.last_update_success and self.coordinator.data:
            return "Online" if self.coordinator.data.get("map_online", False) else "Offline"
        return "Offline"
