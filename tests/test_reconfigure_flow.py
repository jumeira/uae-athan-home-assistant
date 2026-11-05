"""Regression checks for the reconfigure flow."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "uae_athan"


class ReconfigureFlowTests(unittest.TestCase):
    """Protect city and area reconfiguration behavior."""

    def test_reconfigure_allows_unique_area_change(self) -> None:
        """The current entry must not trigger a unique ID mismatch abort."""
        source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")

        self.assertNotIn("_abort_if_unique_id_mismatch()", source)
        self.assertIn("config_entry.entry_id != entry.entry_id", source)
        self.assertIn("config_entry.unique_id == unique_id", source)

    def test_duplicate_area_abort_is_localized(self) -> None:
        """Duplicate-area rejection must have user-facing text in every locale."""
        for relative in (
            "strings.json",
            "translations/en.json",
            "translations/ar.json",
        ):
            payload = json.loads((INTEGRATION / relative).read_text(encoding="utf-8"))
            message = payload["config"]["abort"].get("area_already_configured")
            self.assertTrue(message, relative)


if __name__ == "__main__":
    unittest.main()
