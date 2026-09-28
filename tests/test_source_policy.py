"""Tests for the strict UAE Athan source policy."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "uae_athan"
    / "source_policy.py"
)
SPEC = importlib.util.spec_from_file_location("uae_athan_source_policy", MODULE_PATH)
assert SPEC and SPEC.loader
SOURCE_POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE_POLICY)
catalog_source_error = SOURCE_POLICY.catalog_source_error
prayer_source_error = SOURCE_POLICY.prayer_source_error


def _catalog_payload() -> dict:
    return {
        "source": {
            "provider": "JUMEIRAPPS_CALCULATED",
            "official": False,
            "method": "uae_praytimes_evidence_v2",
            "mode": "mixed",
            "allowedProviders": ["JUMEIRAPPS_CALCULATED", "IACAD"],
            "perpetual_table_areas": [1, 2, 3],
        }
    }


def _calculated_payload() -> dict:
    return {
        "source": {
            "provider": "JUMEIRAPPS_CALCULATED",
            "official": False,
            "method": "uae_praytimes_evidence_v2",
            "mode": "calculated",
            "allowedProviders": ["JUMEIRAPPS_CALCULATED"],
            "contains_calculated": True,
        },
        "days": [
            {
                "source": {
                    "provider": "JUMEIRAPPS_CALCULATED",
                    "method": "uae_praytimes_evidence_v2",
                },
                "generated_from": {
                    "mode": "model",
                    "model_id": "uae_praytimes_evidence_v2",
                    "official_table": False,
                },
            }
        ],
    }


def _perpetual_payload() -> dict:
    return {
        "source": {
            "provider": "IACAD",
            "official": False,
            "mode": "perpetual_table",
            "allowedProviders": ["IACAD"],
            "contains_calculated": False,
        },
        "days": [
            {
                "source": {"provider": "IACAD"},
                "generated_from": {
                    "mode": "table",
                    "table": "perpetual_gregorian",
                    "provider": "IACAD",
                },
            }
        ],
    }


class SourcePolicyTest(unittest.TestCase):
    """Verify accepted sources and important rejection cases."""

    def test_accepts_mixed_catalogue(self) -> None:
        self.assertIsNone(catalog_source_error(_catalog_payload()))

    def test_rejects_unknown_catalogue_provider(self) -> None:
        payload = _catalog_payload()
        payload["source"]["allowedProviders"].append("UNKNOWN")
        self.assertIsNotNone(catalog_source_error(payload))

    def test_accepts_perpetual_table_only_for_dubai_areas(self) -> None:
        for area_id in ("1", "2", "3"):
            self.assertIsNone(prayer_source_error(_perpetual_payload(), area_id))
        self.assertIsNotNone(prayer_source_error(_perpetual_payload(), "35"))

    def test_accepts_calculated_source_for_other_areas(self) -> None:
        self.assertIsNone(prayer_source_error(_calculated_payload(), "35"))
        self.assertIsNone(prayer_source_error(_calculated_payload(), "4"))

    def test_rejects_calculation_for_dubai_areas(self) -> None:
        self.assertIsNotNone(prayer_source_error(_calculated_payload(), "1"))

    def test_rejects_tampered_day_metadata(self) -> None:
        payload = _perpetual_payload()
        payload["days"][0]["generated_from"]["table"] = "other"
        self.assertIsNotNone(prayer_source_error(payload, "1"))

    def test_rejects_missing_or_malformed_days(self) -> None:
        payload = _calculated_payload()
        payload["days"] = []
        self.assertIsNotNone(prayer_source_error(payload, "35"))
        payload["days"] = ["invalid"]
        self.assertIsNotNone(prayer_source_error(payload, "35"))


if __name__ == "__main__":
    unittest.main()
