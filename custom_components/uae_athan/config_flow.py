"""Config flow for UAE Athan."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import UaeAthanApiClient, UaeAthanApiError, UaeAthanSourceError
from .const import (
    CONF_AREA_ID,
    CONF_BACKEND_URL,
    CONF_FAJR_AUDIO_ID,
    CONF_GENERAL_AUDIO_ID,
    CONF_LOOKAHEAD_DAYS,
    CONF_REFRESH_INTERVAL_HOURS,
    DEFAULT_AREA_ID,
    DEFAULT_BACKEND_URL,
    DEFAULT_FAJR_AUDIO_ID,
    DEFAULT_GENERAL_AUDIO_ID,
    DEFAULT_LOOKAHEAD_DAYS,
    DEFAULT_REFRESH_INTERVAL_HOURS,
    DOMAIN,
    entry_value,
)


class UaeAthanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UAE Athan."""

    VERSION = 2

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Set up UAE Athan from the UI."""
        errors: dict[str, str] = {}
        defaults = user_input or {}
        backend_url = str(defaults.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL)).rstrip(
            "/"
        )
        area_options, audio_options = await self._async_remote_options(backend_url)

        if user_input is not None:
            try:
                area = await self._async_validate_input(user_input)
            except UaeAthanSourceError:
                errors["base"] = "invalid_source"
            except UaeAthanApiError:
                errors["base"] = "cannot_connect"
            else:
                area_id = str(user_input[CONF_AREA_ID])
                await self.async_set_unique_id(f"{backend_url}:{area_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._area_title(area, area_id),
                    data={
                        CONF_BACKEND_URL: backend_url,
                        CONF_AREA_ID: area_id,
                        "area": area,
                    },
                    options={
                        CONF_LOOKAHEAD_DAYS: int(user_input[CONF_LOOKAHEAD_DAYS]),
                        CONF_REFRESH_INTERVAL_HOURS: int(
                            user_input[CONF_REFRESH_INTERVAL_HOURS]
                        ),
                        CONF_FAJR_AUDIO_ID: str(user_input[CONF_FAJR_AUDIO_ID]),
                        CONF_GENERAL_AUDIO_ID: str(user_input[CONF_GENERAL_AUDIO_ID]),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(defaults, area_options, audio_options),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return UaeAthanOptionsFlow()

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Change the city or area used by this config entry."""
        entry = self._get_reconfigure_entry()
        backend_url = str(entry.data.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL))
        client = self._client(backend_url)
        errors: dict[str, str] = {}
        areas: list[dict[str, Any]] = []
        try:
            areas = await client.async_get_areas()
        except UaeAthanSourceError:
            errors["base"] = "invalid_source"
        except UaeAthanApiError:
            errors["base"] = "cannot_connect"

        if user_input is not None and not errors:
            area_id = str(user_input[CONF_AREA_ID])
            area = next(
                (item for item in areas if self._area_id(item) == area_id), None
            )
            if area is None:
                errors["base"] = "cannot_connect"
            else:
                unique_id = f"{backend_url.rstrip('/')}:{area_id}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch()
                self.hass.config_entries.async_update_entry(
                    entry,
                    unique_id=unique_id,
                    title=self._area_title(area, area_id),
                    data={
                        **entry.data,
                        CONF_AREA_ID: area_id,
                        "area": area,
                    },
                )
                return self.async_abort(reason="reconfigure_successful")

        area_options = self._area_options(areas)
        area_default = str(entry.data.get(CONF_AREA_ID, DEFAULT_AREA_ID))
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AREA_ID, default=area_default): (
                        vol.In(area_options) if area_options else str
                    )
                }
            ),
            errors=errors,
        )

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        client = self._client(str(user_input[CONF_BACKEND_URL]))
        areas = await client.async_get_areas()
        area_id = str(user_input[CONF_AREA_ID])
        for area in areas:
            if self._area_id(area) == area_id:
                return area
        raise UaeAthanApiError("Selected area is no longer available.")

    async def _async_remote_options(
        self, backend_url: str
    ) -> tuple[dict[str, str], dict[str, str]]:
        client = self._client(backend_url)
        areas: list[dict[str, Any]] = []
        settings: dict[str, Any] = {}
        try:
            areas = await client.async_get_areas()
            settings = await client.async_get_athan_settings()
        except UaeAthanApiError:
            pass
        return self._area_options(areas), self._audio_options(settings)

    def _client(self, backend_url: str) -> UaeAthanApiClient:
        return UaeAthanApiClient(async_get_clientsession(self.hass), backend_url)

    @staticmethod
    def _build_schema(
        defaults: dict[str, Any],
        area_options: dict[str, str],
        audio_options: dict[str, str],
        *,
        include_backend: bool = True,
        include_area: bool = True,
    ) -> vol.Schema:
        area_default = str(defaults.get(CONF_AREA_ID, DEFAULT_AREA_ID))
        if area_options and area_default not in area_options:
            area_default = next(iter(area_options))

        fields: dict[Any, Any] = {}
        if include_backend:
            fields[
                vol.Required(
                    CONF_BACKEND_URL,
                    default=defaults.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL),
                )
            ] = str
        if include_area:
            fields[vol.Required(CONF_AREA_ID, default=area_default)] = (
                vol.In(area_options) if area_options else str
            )
        fields.update(
            {
                vol.Required(
                    CONF_FAJR_AUDIO_ID,
                    default=defaults.get(CONF_FAJR_AUDIO_ID, DEFAULT_FAJR_AUDIO_ID),
                ): vol.In(audio_options),
                vol.Required(
                    CONF_GENERAL_AUDIO_ID,
                    default=defaults.get(
                        CONF_GENERAL_AUDIO_ID, DEFAULT_GENERAL_AUDIO_ID
                    ),
                ): vol.In(audio_options),
                vol.Required(
                    CONF_LOOKAHEAD_DAYS,
                    default=defaults.get(CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS),
                ): vol.All(vol.Coerce(int), vol.Range(min=7, max=70)),
                vol.Required(
                    CONF_REFRESH_INTERVAL_HOURS,
                    default=defaults.get(
                        CONF_REFRESH_INTERVAL_HOURS,
                        DEFAULT_REFRESH_INTERVAL_HOURS,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            }
        )
        return vol.Schema(fields)

    @classmethod
    def _area_options(cls, areas: list[dict[str, Any]]) -> dict[str, str]:
        options: dict[str, str] = {}
        for area in areas:
            area_id = cls._area_id(area)
            if area_id:
                options[area_id] = cls._area_title(area, area_id)
        return options

    @staticmethod
    def _audio_options(settings: dict[str, Any]) -> dict[str, str]:
        defaults = {
            DEFAULT_FAJR_AUDIO_ID: "أذان الفجر / Fajr Athan",
            DEFAULT_GENERAL_AUDIO_ID: "أذان 1 / Athan 1",
        }
        library = settings.get("audio_library", {})
        items = library.get("items", []) if isinstance(library, dict) else []
        if not isinstance(items, list):
            return defaults

        options: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict) or item.get("category") != "adhan":
                continue
            item_id = str(item.get("id") or "")
            if not item_id or not item.get("url"):
                continue
            title_ar = str(item.get("title_ar") or item_id)
            title_en = str(item.get("title_en") or item_id)
            options[item_id] = f"{title_ar} / {title_en}"
        return options or defaults

    @staticmethod
    def _area_id(area: dict[str, Any]) -> str:
        return str(area.get("areaID") or area.get("area_id") or "")

    @staticmethod
    def _area_title(area: dict[str, Any], fallback: str) -> str:
        title_ar = str(area.get("areaNameAr") or area.get("area_name_ar") or "")
        title_en = str(area.get("areaNameEn") or area.get("area_name_en") or "")
        if title_ar and title_en:
            return f"{title_ar} / {title_en}"
        return title_ar or title_en or fallback


class UaeAthanOptionsFlow(config_entries.OptionsFlow):
    """Handle UAE Athan options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.FlowResult:
        """Change area, audio choices, and cache settings."""
        errors: dict[str, str] = {}
        backend_url = str(
            self.config_entry.data.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL)
        )
        client = UaeAthanApiClient(async_get_clientsession(self.hass), backend_url)
        settings: dict[str, Any] = {}
        try:
            settings = await client.async_get_athan_settings()
        except UaeAthanSourceError:
            errors["base"] = "invalid_source"
        except UaeAthanApiError:
            pass
        audio_options = UaeAthanConfigFlow._audio_options(settings)
        for key in (CONF_FAJR_AUDIO_ID, CONF_GENERAL_AUDIO_ID):
            selected = str(entry_value(self.config_entry, key, ""))
            if selected:
                audio_options.setdefault(selected, selected)

        if user_input is not None:
            if errors:
                pass
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_LOOKAHEAD_DAYS: int(user_input[CONF_LOOKAHEAD_DAYS]),
                        CONF_REFRESH_INTERVAL_HOURS: int(
                            user_input[CONF_REFRESH_INTERVAL_HOURS]
                        ),
                        CONF_FAJR_AUDIO_ID: str(user_input[CONF_FAJR_AUDIO_ID]),
                        CONF_GENERAL_AUDIO_ID: str(user_input[CONF_GENERAL_AUDIO_ID]),
                    },
                )

        defaults = {
            CONF_LOOKAHEAD_DAYS: entry_value(
                self.config_entry, CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS
            ),
            CONF_REFRESH_INTERVAL_HOURS: entry_value(
                self.config_entry,
                CONF_REFRESH_INTERVAL_HOURS,
                DEFAULT_REFRESH_INTERVAL_HOURS,
            ),
            CONF_FAJR_AUDIO_ID: entry_value(
                self.config_entry, CONF_FAJR_AUDIO_ID, DEFAULT_FAJR_AUDIO_ID
            ),
            CONF_GENERAL_AUDIO_ID: entry_value(
                self.config_entry, CONF_GENERAL_AUDIO_ID, DEFAULT_GENERAL_AUDIO_ID
            ),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=UaeAthanConfigFlow._build_schema(
                defaults,
                {},
                audio_options,
                include_backend=False,
                include_area=False,
            ),
            errors=errors,
        )
