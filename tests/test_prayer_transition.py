"""Regression checks for next-prayer transitions."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INIT_SOURCE = ROOT / "custom_components" / "uae_athan" / "__init__.py"


class PrayerTransitionTests(unittest.TestCase):
    """Protect state updates at prayer boundaries."""

    def test_prayer_event_updates_coordinator_listeners(self) -> None:
        """Next-prayer sensors must refresh as soon as a prayer starts."""
        source = INIT_SOURCE.read_text(encoding="utf-8")
        callback_start = source.index("def _fire_event")
        callback_end = source.index("return _fire_event", callback_start)
        callback_source = source[callback_start:callback_end]

        fire_position = callback_source.index("hass.bus.async_fire")
        update_position = callback_source.index("coordinator.async_update_listeners()")
        self.assertLess(fire_position, update_position)


if __name__ == "__main__":
    unittest.main()
