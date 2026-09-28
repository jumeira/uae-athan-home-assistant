#!/usr/bin/env python3
"""Validate the UAE Athan Home Assistant release without HA dependencies."""

from __future__ import annotations

import json
import py_compile
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "uae_athan"
sys.path.insert(0, str(INTEGRATION))
from source_policy import catalog_source_error, prayer_source_error  # noqa: E402


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {err}")


def validate_files() -> None:
    required = [
        "__init__.py",
        "api.py",
        "config_flow.py",
        "const.py",
        "coordinator.py",
        "sensor.py",
        "source_policy.py",
        "manifest.json",
        "strings.json",
        "services.yaml",
        "icons.json",
        "translations/ar.json",
        "translations/en.json",
        "brand/icon.png",
        "brand/logo.png",
    ]
    for relative in required:
        if not (INTEGRATION / relative).is_file():
            fail(f"missing {relative}")

    manifest = load_json(INTEGRATION / "manifest.json")
    if manifest.get("domain") != "uae_athan":
        fail("manifest domain must be uae_athan")
    if manifest.get("version") != "0.3.0":
        fail("manifest version must be 0.3.0")
    if manifest.get("codeowners") != ["@jumeira"]:
        fail("manifest codeowners must contain @jumeira")
    if not manifest.get("issue_tracker"):
        fail("manifest must define issue_tracker")

    load_json(ROOT / "hacs.json")
    strings = load_json(INTEGRATION / "strings.json")
    load_json(INTEGRATION / "icons.json")
    for language in ("ar", "en"):
        translation = load_json(INTEGRATION / "translations" / f"{language}.json")
        sensors = translation.get("entity", {}).get("sensor", {})
        if len(sensors) != 7:
            fail(f"{language} must translate all 7 sensors")
    if len(strings.get("entity", {}).get("sensor", {})) != 7:
        fail("strings.json must define all 7 sensors")

    for path in sorted(INTEGRATION.glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def validate_live_api() -> None:
    base = "https://jumeirapps.com/uae-athan-api/"
    for endpoint in ("areas.php", "athan-settings.php"):
        payload = fetch_json(base + endpoint)
        if error := catalog_source_error(payload):
            fail(f"{endpoint}: {error}")
        if endpoint == "areas.php" and len(payload.get("areas", [])) != 13:
            fail("areas.php must return 13 areas")

    areas_payload = fetch_json(base + "areas.php")
    area_ids = [
        str(area.get("areaID") or area.get("area_id") or "")
        for area in areas_payload.get("areas", [])
        if isinstance(area, dict)
    ]
    if len(area_ids) != 13 or any(not area_id for area_id in area_ids):
        fail("areas.php must provide 13 usable area IDs")

    today = date.today().isoformat()
    for area_id in area_ids:
        query = urlencode({"areaId": area_id, "from": today, "to": today})
        payload = fetch_json(f"{base}prayer-times.php?{query}")
        if error := prayer_source_error(payload, area_id):
            fail(f"prayer-times.php area {area_id}: {error}")
        if len(payload.get("days", [])) != 1:
            fail(f"prayer-times.php area {area_id} must return one day")


def fetch_json(url: str) -> dict:
    """Fetch one JSON object for release validation."""
    with urlopen(url, timeout=20) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        fail(f"{url} did not return a JSON object")
    return payload


def main() -> None:
    validate_files()
    validate_live_api()
    print("OK: release files, translations, Python syntax, and live source policy")


if __name__ == "__main__":
    main()
