"""UAE Athan custom integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import UaeAthanApiClient
from .const import (
    CONF_BACKEND_URL,
    DOMAIN,
    EVENT_UAE_ATHAN,
    PLATFORMS,
    PRAYER_BY_ID,
    PRAYERS,
    SERVICE_REFRESH,
    SERVICE_TEST_PRAYER,
)
from .coordinator import UaeAthanCoordinator

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PRAYER_ID = "prayer_id"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, _config: dict[str, Any]) -> bool:
    """Register UAE Athan actions."""
    hass.data.setdefault(DOMAIN, {})

    async def _async_refresh(call: ServiceCall) -> None:
        coordinator = _coordinator_for_call(hass, call)
        await coordinator.async_request_refresh()

    async def _async_test_prayer(call: ServiceCall) -> None:
        coordinator = _coordinator_for_call(hass, call)
        prayer_id = str(call.data[ATTR_PRAYER_ID])
        day = coordinator.today_day
        if not day:
            await coordinator.async_request_refresh()
            day = coordinator.today_day
        if not day:
            raise HomeAssistantError("No prayer data is available for today.")
        now = datetime.now(coordinator.time_zone)
        payload = coordinator.event_payload(day, prayer_id, now)
        payload["type"] = "prayer_time_test"
        payload["test"] = True
        payload["due_at"] = now.isoformat()
        hass.bus.async_fire(EVENT_UAE_ATHAN, payload)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        _async_refresh,
        schema=vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_PRAYER,
        _async_test_prayer,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
                vol.Required(ATTR_PRAYER_ID): vol.In(PRAYER_BY_ID),
            }
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UAE Athan from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    client = UaeAthanApiClient(session, entry.data[CONF_BACKEND_URL])
    coordinator = UaeAthanCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "unsub_events": [],
    }

    _async_schedule_prayer_events(hass, entry)
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: _async_schedule_prayer_events(hass, entry)
        )
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload UAE Athan."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        _cancel_scheduled_events(data)
    return unload_ok


@callback
def _async_schedule_prayer_events(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: UaeAthanCoordinator = data["coordinator"]
    _cancel_scheduled_events(data)

    now = dt_util.utcnow()
    unsubs: list[CALLBACK_TYPE] = []
    for day in coordinator.data_days:
        for prayer in PRAYERS:
            due_at = coordinator.get_day_prayer_datetime(day, prayer["id"])
            if not due_at:
                continue
            due_at_utc = dt_util.as_utc(due_at)
            if due_at_utc <= now + timedelta(seconds=1):
                continue
            unsubs.append(
                async_track_point_in_time(
                    hass,
                    _make_event_callback(hass, coordinator, day, prayer["id"], due_at),
                    due_at_utc,
                )
            )

    data["unsub_events"] = unsubs


def _make_event_callback(
    hass: HomeAssistant,
    coordinator: UaeAthanCoordinator,
    day: dict[str, Any],
    prayer_id: str,
    due_at: datetime,
):
    @callback
    def _fire_event(_now: datetime) -> None:
        hass.bus.async_fire(
            EVENT_UAE_ATHAN,
            coordinator.event_payload(day, prayer_id, due_at),
        )

    return _fire_event


@callback
def _cancel_scheduled_events(data: dict[str, Any]) -> None:
    for unsub in data.get("unsub_events", []):
        unsub()
    data["unsub_events"] = []


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after an option or area changes."""
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinator_for_call(
    hass: HomeAssistant, call: ServiceCall
) -> UaeAthanCoordinator:
    """Resolve a service call to a loaded UAE Athan coordinator."""
    entries = hass.data.get(DOMAIN, {})
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id:
        data = entries.get(entry_id)
        if not data:
            raise HomeAssistantError("The selected UAE Athan entry is not loaded.")
        return data["coordinator"]
    if len(entries) != 1:
        raise HomeAssistantError("Select a UAE Athan config entry.")
    return next(iter(entries.values()))["coordinator"]
