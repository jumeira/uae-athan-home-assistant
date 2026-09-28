"""Strict source policy for Jumeirapps UAE Athan responses."""

from __future__ import annotations

from typing import Any

CALCULATED_PROVIDER = "JUMEIRAPPS_CALCULATED"
CALCULATED_METHOD = "uae_praytimes_evidence_v2"
CALCULATED_MODE = "calculated"
IACAD_PROVIDER = "IACAD"
MIXED_MODE = "mixed"
PERPETUAL_MODE = "perpetual_table"
PERPETUAL_TABLE = "perpetual_gregorian"
PERPETUAL_AREA_IDS = frozenset({"1", "2", "3"})


def catalog_source_error(payload: dict[str, Any]) -> str | None:
    """Return an error when shared catalogue metadata violates the policy."""
    source = _source(payload)
    if source is None:
        return "Backend response has no source metadata."
    if source.get("provider") != CALCULATED_PROVIDER:
        return "Catalogue provider is not Jumeirapps."
    if source.get("method") != CALCULATED_METHOD:
        return "Catalogue method is not the approved UAE Athan v2 engine."
    if source.get("mode") != MIXED_MODE:
        return "Catalogue does not declare the approved mixed source mode."
    if source.get("official") is not False:
        return "Catalogue must be marked as non-official."
    if _provider_set(source) != {CALCULATED_PROVIDER, IACAD_PROVIDER}:
        return "Catalogue allowedProviders does not match the approved providers."
    if _area_id_set(source.get("perpetual_table_areas")) != PERPETUAL_AREA_IDS:
        return "Catalogue perpetual-table areas do not match the approved areas."
    return None


def prayer_source_error(payload: dict[str, Any], area_id: str) -> str | None:
    """Return an error when prayer-time metadata violates the area policy."""
    normalized_area_id = str(area_id)
    if normalized_area_id in PERPETUAL_AREA_IDS:
        return _perpetual_source_error(payload)
    return _calculated_source_error(payload)


def _perpetual_source_error(payload: dict[str, Any]) -> str | None:
    source = _source(payload)
    if source is None:
        return "Prayer response has no source metadata."
    if source.get("provider") != IACAD_PROVIDER:
        return "Dubai-jurisdiction areas must use the IACAD perpetual table."
    if source.get("mode") != PERPETUAL_MODE:
        return "Dubai-jurisdiction areas are not in perpetual-table mode."
    if source.get("official") is not False:
        return "Republished table output must be marked as non-official."
    if source.get("contains_calculated") is not False:
        return "Perpetual-table output unexpectedly contains calculated days."
    if _provider_set(source) != {IACAD_PROVIDER}:
        return "Perpetual-table allowedProviders is invalid."

    days = _days(payload)
    if days is None:
        return "Perpetual-table output has no valid prayer days."
    for day in days:
        day_source = day.get("source")
        generated = day.get("generated_from")
        if (
            not isinstance(day_source, dict)
            or day_source.get("provider") != IACAD_PROVIDER
        ):
            return "A perpetual-table day is not attributed to IACAD."
        if not isinstance(generated, dict):
            return "A perpetual-table day has no generation metadata."
        if (
            generated.get("mode") != "table"
            or generated.get("table") != PERPETUAL_TABLE
            or generated.get("provider") != IACAD_PROVIDER
        ):
            return "A perpetual-table day has unexpected generation metadata."
    return None


def _calculated_source_error(payload: dict[str, Any]) -> str | None:
    source = _source(payload)
    if source is None:
        return "Prayer response has no source metadata."
    if source.get("provider") != CALCULATED_PROVIDER:
        return "Calculated area provider is not Jumeirapps."
    if source.get("method") != CALCULATED_METHOD:
        return "Calculated area method is not the approved UAE Athan v2 engine."
    if source.get("mode") != CALCULATED_MODE:
        return "Calculated area is not in calculated mode."
    if source.get("official") is not False:
        return "Calculated output must be marked as non-official."
    if source.get("contains_calculated") is not True:
        return "Calculated output does not declare calculated days."
    if _provider_set(source) != {CALCULATED_PROVIDER}:
        return "Calculated allowedProviders is invalid."

    days = _days(payload)
    if days is None:
        return "Calculated output has no valid prayer days."
    for day in days:
        day_source = day.get("source")
        generated = day.get("generated_from")
        if not isinstance(day_source, dict) or (
            day_source.get("provider") != CALCULATED_PROVIDER
            or day_source.get("method") != CALCULATED_METHOD
        ):
            return "A calculated day has unexpected source metadata."
        if not isinstance(generated, dict):
            return "A calculated day has no generation metadata."
        if (
            generated.get("mode") != "model"
            or generated.get("model_id") != CALCULATED_METHOD
            or generated.get("official_table") is not False
        ):
            return "A calculated day has unexpected generation metadata."
    return None


def _source(payload: dict[str, Any]) -> dict[str, Any] | None:
    source = payload.get("source")
    return source if isinstance(source, dict) else None


def _days(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    days = payload.get("days")
    if (
        not isinstance(days, list)
        or not days
        or not all(isinstance(day, dict) for day in days)
    ):
        return None
    return days


def _provider_set(source: dict[str, Any]) -> set[str]:
    providers = source.get("allowedProviders")
    if not isinstance(providers, list):
        return set()
    return {str(provider) for provider in providers}


def _area_id_set(value: Any) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(str(area_id) for area_id in value)
