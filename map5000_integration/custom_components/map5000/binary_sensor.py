"""Binary sensor entities – one per MAP5000 point (Melder), showing active state."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
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
    points = (coordinator.data or {}).get("points", [])
    async_add_entities(
        Map5000PointActive(coordinator, p) for p in points if p.get("@self")
    )


def _slug(siid: str) -> str:
    return siid.replace(".", "_").replace("/", "_").strip("_")


class Map5000PointActive(CoordinatorEntity, BinarySensorEntity):
    """Shows whether a MAP5000 detector (Melder) is active (ausgelöst)."""

    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: Map5000Coordinator, point_data: dict) -> None:
        super().__init__(coordinator)
        self._siid: str = point_data["@self"].lstrip("/")
        name = point_data.get("name") or self._siid
        self._attr_name = name
        self._attr_unique_id = f"map5000_point_{_slug(self._siid)}"

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
        return bool(p.get("active")) if p is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        p = self._point
        if not p:
            return {}
        return {
            "status": p.get("status_label", "—"),
            "sperren": p.get("sperren", False),
            "enabled": p.get("enabled", True),
            "siid": self._siid,
        }
