#!/usr/bin/env python3
"""Generate platform-specific icons from assets/icon-source.png.

Regenerate after replacing the source image:

    python3 scripts/build_icons.py

Produces:
    assets/icon.icns  (macOS app bundle)
    assets/icon.ico   (Windows .exe)
    assets/icon.png   (runtime QIcon, also Linux)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icon-source.png"
ICNS = ROOT / "assets" / "icon.icns"
ICO = ROOT / "assets" / "icon.ico"
PNG = ROOT / "assets" / "icon.png"

ICNS_SIZES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]
ICO_SIZES = [16, 32, 48, 64, 128, 256]


def build_icns(src: Image.Image) -> None:
    if sys.platform != "darwin":
        print("Skipping .icns (iconutil only available on macOS)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for name, size in ICNS_SIZES:
            src.resize((size, size), Image.LANCZOS).save(iconset / name, "PNG")
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS)],
            check=True,
        )
    print(f"Wrote {ICNS.relative_to(ROOT)}")


def build_ico(src: Image.Image) -> None:
    src.save(ICO, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    print(f"Wrote {ICO.relative_to(ROOT)}")


def build_runtime_png(src: Image.Image) -> None:
    shutil.copyfile(SOURCE, PNG)
    print(f"Wrote {PNG.relative_to(ROOT)}")


def main() -> None:
    if not SOURCE.exists():
        sys.exit(f"Source image not found: {SOURCE}")
    with Image.open(SOURCE) as raw:
        src = raw.convert("RGBA")
        build_icns(src)
        build_ico(src)
        build_runtime_png(src)


if __name__ == "__main__":
    main()
