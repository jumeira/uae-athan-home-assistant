"""Sensors for UAE Athan."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_UAE_ATHAN, PRAYERS
from .coordinator import UaeAthanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UAE Athan sensors."""
    coordinator: UaeAthanCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = [
        UaeAthanNextPrayerSensor(coordinator),
        UaeAthanNextPrayerTimeSensor(coordinator),
    ]
    entities.extend(UaeAthanPrayerTimeSensor(coordinator, prayer) for prayer in PRAYERS)
    async_add_entities(entities)


class UaeAthanBaseSensor(CoordinatorEntity[UaeAthanCoordinator], SensorEntity):
    """Base sensor for UAE Athan."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UaeAthanCoordinator) -> None:
        super().__init__(coordinator)
        self._entry = coordinator.entry
        area = coordinator.entry.data.get("area")
        area_name = None
        if isinstance(area, dict):
            area_name = area.get("areaNameAr") or area.get("areaNameEn")

        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "UAE Athan",
            "manufacturer": "Jumeirapps",
            "model": area_name or "UAE Prayer Times",
        }


class UaeAthanNextPrayerSensor(UaeAthanBaseSensor):
    """Sensor exposing the next prayer."""

    _attr_icon = "mdi:mosque"
    _attr_translation_key = "next_prayer"

    def __init__(self, coordinator: UaeAthanCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry.entry_id}_next_prayer"

    @property
    def native_value(self) -> str | None:
        item = self.coordinator.next_prayer()
        if not item:
            return None
        return str(item.get("prayer_ar") or item.get("prayer") or item.get("prayer_id"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self.coordinator.next_prayer()
        if not item:
            return {}
        clean = dict(item)
        clean.pop("due_at_datetime", None)
        clean["event_type"] = EVENT_UAE_ATHAN
        return clean


class UaeAthanNextPrayerTimeSensor(UaeAthanBaseSensor):
    """Timestamp sensor exposing the next prayer due time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"
    _attr_translation_key = "next_prayer_time"

    def __init__(self, coordinator: UaeAthanCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._entry.entry_id}_next_prayer_time"

    @property
    def native_value(self) -> datetime | None:
        item = self.coordinator.next_prayer()
        if not item:
            return None
        value = item.get("due_at_datetime")
        return value if isinstance(value, datetime) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self.coordinator.next_prayer()
        if not item:
            return {}
        return {
            "prayer_id": item.get("prayer_id"),
            "prayer": item.get("prayer"),
            "prayer_ar": item.get("prayer_ar"),
            "audio_url": item.get("audio_url"),
        }


class UaeAthanPrayerTimeSensor(UaeAthanBaseSensor):
    """Timestamp sensor for one of today's prayer times."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: UaeAthanCoordinator, prayer: dict[str, str]
    ) -> None:
        super().__init__(coordinator)
        self._prayer = prayer
        self._attr_name = f"{prayer['name_en']} time"
        self._attr_translation_key = f"{prayer['id']}_time"
        self._attr_unique_id = f"{self._entry.entry_id}_{prayer['id']}_time"
        self._attr_icon = "mdi:clock-time-four-outline"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.today_prayer_datetime(self._prayer["id"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        day = self.coordinator.today_day
        due_at = self.native_value
        if not day or not due_at:
            return {}
        return self.coordinator.event_payload(day, self._prayer["id"], due_at)
