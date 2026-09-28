"""Constants for the UAE Athan integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "uae_athan"
PLATFORMS = [Platform.SENSOR]

CONF_BACKEND_URL = "backend_url"
CONF_AREA_ID = "area_id"
CONF_LOOKAHEAD_DAYS = "lookahead_days"
CONF_REFRESH_INTERVAL_HOURS = "refresh_interval_hours"
CONF_FAJR_AUDIO_ID = "fajr_audio_id"
CONF_GENERAL_AUDIO_ID = "general_audio_id"

DEFAULT_BACKEND_URL = "https://jumeirapps.com/uae-athan-api"
DEFAULT_AREA_ID = "1"
DEFAULT_LOOKAHEAD_DAYS = 45
DEFAULT_REFRESH_INTERVAL_HOURS = 6
DEFAULT_FAJR_AUDIO_ID = "adhan_fajr"
DEFAULT_GENERAL_AUDIO_ID = "adhan_1"

EVENT_UAE_ATHAN = "uae_athan_event"

SERVICE_REFRESH = "refresh"
SERVICE_TEST_PRAYER = "test_prayer"

UAE_TIME_ZONE = "Asia/Dubai"

PRAYERS = [
    {"id": "fajr", "name_en": "Fajr", "name_ar": "الفجر"},
    {"id": "dhuhr", "name_en": "Dhuhr", "name_ar": "الظهر"},
    {"id": "asr", "name_en": "Asr", "name_ar": "العصر"},
    {"id": "maghrib", "name_en": "Maghrib", "name_ar": "المغرب"},
    {"id": "isha", "name_en": "Isha", "name_ar": "العشاء"},
]

PRAYER_BY_ID = {prayer["id"]: prayer for prayer in PRAYERS}


def entry_value(entry, key: str, default=None):
    """Return an option value, falling back to config-entry data."""
    return entry.options.get(key, entry.data.get(key, default))
