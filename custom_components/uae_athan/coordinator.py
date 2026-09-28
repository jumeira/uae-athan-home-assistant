"""Data coordinator for UAE Athan."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UaeAthanApiClient, UaeAthanApiError
from .const import (
    CONF_AREA_ID,
    CONF_FAJR_AUDIO_ID,
    CONF_GENERAL_AUDIO_ID,
    CONF_LOOKAHEAD_DAYS,
    CONF_REFRESH_INTERVAL_HOURS,
    DEFAULT_FAJR_AUDIO_ID,
    DEFAULT_GENERAL_AUDIO_ID,
    DEFAULT_LOOKAHEAD_DAYS,
    DEFAULT_REFRESH_INTERVAL_HOURS,
    DOMAIN,
    PRAYER_BY_ID,
    PRAYERS,
    UAE_TIME_ZONE,
    entry_value,
)

_LOGGER = logging.getLogger(__name__)


class UaeAthanCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and normalize UAE Athan data for Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: UaeAthanApiClient,
    ) -> None:
        self.entry = entry
        self.client = client
        self.time_zone = ZoneInfo(UAE_TIME_ZONE)

        refresh_hours = int(
            entry_value(
                entry, CONF_REFRESH_INTERVAL_HOURS, DEFAULT_REFRESH_INTERVAL_HOURS
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=max(1, refresh_hours)),
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        area_id = str(self.entry.data.get(CONF_AREA_ID, ""))
        if not area_id:
            raise UaeAthanApiError("Missing area id.")

        today = datetime.now(self.time_zone).date()
        lookahead = int(
            entry_value(self.entry, CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS)
        )
        lookahead = min(max(lookahead, 7), 70)
        end = today + timedelta(days=lookahead)

        try:
            payload = await self.client.async_get_prayer_times(area_id, today, end)
        except UaeAthanApiError as err:
            raise UpdateFailed(f"Unable to update UAE Athan: {err}") from err

        settings = await self._async_get_settings_safely()

        days = payload.get("days", [])
        if not isinstance(days, list) or not days:
            raise UpdateFailed("UAE Athan returned no prayer days.")

        return {
            "area_id": area_id,
            "area": self.entry.data.get("area"),
            "source": payload.get("source", {}),
            "hash": payload.get("hash"),
            "updated_at": payload.get("updated_at"),
            "method": payload.get("source", {}).get("method"),
            "days": days,
            "audio_library": self._normalize_audio_library(
                settings.get("audio_library")
            ),
        }

    async def _async_get_settings_safely(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_athan_settings()
        except UaeAthanApiError:
            return {}

    @property
    def today_day(self) -> dict[str, Any] | None:
        today_key = datetime.now(self.time_zone).date().isoformat()
        for day in self.data_days:
            if day.get("date") == today_key:
                return day
        return None

    @property
    def data_days(self) -> list[dict[str, Any]]:
        if not self.data:
            return []
        days = self.data.get("days", [])
        return days if isinstance(days, list) else []

    def get_day_prayer_datetime(
        self,
        day: dict[str, Any],
        prayer_id: str,
    ) -> datetime | None:
        date_value = day.get("date")
        time_value = self._get_prayer_time(day, prayer_id)
        if not isinstance(date_value, str) or not isinstance(time_value, str):
            return None

        try:
            return datetime.fromisoformat(f"{date_value}T{time_value}:00").replace(
                tzinfo=self.time_zone
            )
        except ValueError:
            return None

    def today_prayer_datetime(self, prayer_id: str) -> datetime | None:
        day = self.today_day
        if not day:
            return None
        return self.get_day_prayer_datetime(day, prayer_id)

    def next_prayer(self) -> dict[str, Any] | None:
        now = datetime.now(self.time_zone)
        next_item: dict[str, Any] | None = None

        for day in self.data_days:
            for prayer in PRAYERS:
                due_at = self.get_day_prayer_datetime(day, prayer["id"])
                if not due_at or due_at <= now:
                    continue
                item = self.event_payload(day, prayer["id"], due_at)
                if next_item is None or due_at < next_item["due_at_datetime"]:
                    item["due_at_datetime"] = due_at
                    next_item = item

        return next_item

    def event_payload(
        self,
        day: dict[str, Any],
        prayer_id: str,
        due_at: datetime,
    ) -> dict[str, Any]:
        prayer = PRAYER_BY_ID.get(prayer_id, {})
        audio = self.audio_for_prayer(prayer_id)
        area = self.data.get("area") if self.data else None
        if not isinstance(area, dict):
            area = {}

        payload = {
            "type": "prayer_time_due",
            "prayer_id": prayer_id,
            "prayer": prayer.get("name_en", prayer_id),
            "prayer_ar": prayer.get("name_ar", prayer_id),
            "date": day.get("date"),
            "time": self._get_prayer_time(day, prayer_id),
            "due_at": due_at.isoformat(),
            "area_id": self.data.get("area_id") if self.data else None,
            "area_name_ar": area.get("areaNameAr") or area.get("area_name_ar"),
            "area_name_en": area.get("areaNameEn") or area.get("area_name_en"),
            "source": self.data.get("source") if self.data else None,
            "method": self.data.get("method") if self.data else None,
            "generated_from": day.get("generated_from"),
        }
        if audio:
            payload["audio_id"] = audio.get("id")
            payload["audio_title"] = audio.get("title_ar") or audio.get("title_en")
            payload["audio_url"] = audio.get("url")
            payload["audio_content_type"] = audio.get("content_type")
        return payload

    def audio_for_prayer(self, prayer_id: str) -> dict[str, Any] | None:
        if not self.data:
            return None
        library = self.data.get("audio_library", {})
        items = library.get("items", []) if isinstance(library, dict) else []
        if not isinstance(items, list):
            return None

        adhans = [
            item
            for item in items
            if isinstance(item, dict)
            and item.get("category") == "adhan"
            and item.get("url")
        ]

        preferred_id = entry_value(
            self.entry,
            CONF_FAJR_AUDIO_ID if prayer_id == "fajr" else CONF_GENERAL_AUDIO_ID,
            DEFAULT_FAJR_AUDIO_ID if prayer_id == "fajr" else DEFAULT_GENERAL_AUDIO_ID,
        )
        for item in adhans:
            if item.get("id") == preferred_id:
                return item

        for item in adhans:
            if prayer_id == "fajr" and item.get("prayer") == "fajr":
                return item

        for item in adhans:
            if not item.get("prayer"):
                return item

        return None

    def _normalize_audio_library(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {"items": []}
        items = value.get("items", [])
        if not isinstance(items, list):
            items = []
        return {
            "updated_at": value.get("updated_at"),
            "items": [
                item for item in items if isinstance(item, dict) and item.get("url")
            ],
        }

    def _get_prayer_time(self, day: dict[str, Any], prayer_id: str) -> str | None:
        times = day.get("times", {})
        if not isinstance(times, dict):
            return None
        value = times.get(prayer_id)
        return value if isinstance(value, str) else None
