"""Jumeirapps API client for UAE Athan."""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .source_policy import catalog_source_error, prayer_source_error


class UaeAthanApiError(Exception):
    """Raised when the Jumeirapps backend cannot be read."""


class UaeAthanSourceError(UaeAthanApiError):
    """Raised when the backend no longer serves the approved v2 engine."""


class UaeAthanApiClient:
    """Small async client for the Jumeirapps UAE Athan backend."""

    def __init__(self, session: ClientSession, backend_url: str) -> None:
        self._session = session
        self._backend_url = backend_url.rstrip("/") + "/"

    async def async_get_areas(self) -> list[dict[str, Any]]:
        """Return the available areas from Jumeirapps."""
        payload = await self._async_get_json("areas.php")
        self._validate_catalog_source(payload)
        areas = payload.get("areas", [])
        if not isinstance(areas, list):
            raise UaeAthanApiError("Invalid areas payload.")
        return areas

    async def async_get_prayer_times(
        self,
        area_id: str,
        start: date,
        end: date,
    ) -> dict[str, Any]:
        """Return prayer times for one area and date range."""
        payload = await self._async_get_json(
            "prayer-times.php",
            {
                "areaId": area_id,
                "from": start.isoformat(),
                "to": end.isoformat(),
            },
        )
        self._validate_prayer_source(payload, area_id)
        return payload

    async def async_get_athan_settings(self) -> dict[str, Any]:
        """Return Athan settings, including the optional audio library."""
        payload = await self._async_get_json("athan-settings.php")
        self._validate_catalog_source(payload)
        settings = payload.get("settings", {})
        if not isinstance(settings, dict):
            return {}
        return settings

    async def _async_get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = urljoin(self._backend_url, endpoint)
        timeout = ClientTimeout(total=15)
        try:
            async with self._session.get(
                url, params=params, timeout=timeout
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, ClientResponseError, TimeoutError, ValueError) as err:
            raise UaeAthanApiError(str(err)) from err

        if not isinstance(payload, dict):
            raise UaeAthanApiError("Invalid JSON payload.")
        if payload.get("ok") is False:
            message = (
                payload.get("message")
                or payload.get("error")
                or "Backend returned an error."
            )
            raise UaeAthanApiError(str(message))
        return payload

    @staticmethod
    def _validate_catalog_source(payload: dict[str, Any]) -> None:
        """Reject catalogue data outside the approved mixed-source policy."""
        error = catalog_source_error(payload)
        if error:
            raise UaeAthanSourceError(error)

    @staticmethod
    def _validate_prayer_source(payload: dict[str, Any], area_id: str) -> None:
        """Reject prayer data outside the approved policy for the area."""
        error = prayer_source_error(payload, area_id)
        if error:
            raise UaeAthanSourceError(error)
