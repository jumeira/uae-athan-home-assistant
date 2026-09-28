#!/usr/bin/env python3
"""Build a deterministic Home Assistant release ZIP."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "uae_athan"
OUTPUT = ROOT / "build" / "uae-athan-home-assistant.zip"


def main() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_release.py")],
        check=True,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in sorted(SOURCE.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = (
                Path("custom_components") / "uae_athan" / path.relative_to(SOURCE)
            )
            info = ZipInfo(str(relative), date_time=(2026, 9, 28, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    print(f"Built {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
