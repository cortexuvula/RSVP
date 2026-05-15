#!/usr/bin/env python3
"""Mask the rounded-rectangle icon footprint onto a transparent canvas.

Run once after dropping in a new opaque source image
(e.g. a JPEG with a white background):

    python3 scripts/mask_icon_source.py path/to/source.jpg

Writes the masked output to assets/icon-source.png. The source's own
anti-aliased rounded-square edge is preserved by chroma-keying white
in the boundary ring; the interior is forced fully opaque so white
artwork elements (text, line art) inside the rounded square keep their
alpha. Re-run scripts/build_icons.py afterwards to regenerate the
platform icons.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "icon-source.png"

# Pixels brighter than this on every channel count as background.
BACKGROUND_THRESHOLD = 245
# Brightness ramp for chroma-keying white: BG_HI -> alpha 0, BG_LO -> alpha 255.
BG_HI = 250
BG_LO = 225
# Inset (px on a 1024 canvas) from the detected bbox used for the "force opaque"
# interior mask. Anything inside this inset is opaque regardless of brightness,
# which protects white artwork inside the rounded square.
INTERIOR_INSET_RATIO = 0.06
# Corner radius for the interior mask, as a fraction of its short side.
INTERIOR_RADIUS_RATIO = 0.16
SUPERSAMPLE = 4


def detect_content_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    gray = image.convert("L").point(lambda p: 0 if p > BACKGROUND_THRESHOLD else 255)
    bbox = gray.getbbox()
    if bbox is None:
        raise SystemExit("No content found in source — image looks fully white.")
    return bbox


def build_rounded_mask(size: tuple[int, int], bbox: tuple[int, int, int, int], radius: int) -> Image.Image:
    """Build a smooth anti-aliased rounded-rectangle alpha mask."""
    w, h = size
    big = Image.new("L", (w * SUPERSAMPLE, h * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(big)
    big_bbox = tuple(c * SUPERSAMPLE for c in bbox)
    draw.rounded_rectangle(big_bbox, radius=radius * SUPERSAMPLE, fill=255)
    return big.resize((w, h), Image.LANCZOS)


def build_chroma_alpha(image: Image.Image) -> Image.Image:
    """Per-pixel alpha derived from luminance — white→0, dark→255, AA gradient between."""
    gray = image.convert("L")
    span = BG_HI - BG_LO

    def ramp(v: int) -> int:
        if v >= BG_HI:
            return 0
        if v <= BG_LO:
            return 255
        return int((BG_HI - v) * 255 / span)

    return gray.point(ramp)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: mask_icon_source.py <source-image>")
    src_path = Path(sys.argv[1])
    if not src_path.is_file():
        sys.exit(f"Source not found: {src_path}")

    with Image.open(src_path) as raw:
        src = raw.convert("RGB")

    bbox = detect_content_bbox(src)
    w, h = src.size
    inset = int(min(w, h) * INTERIOR_INSET_RATIO)
    interior_bbox = (bbox[0] + inset, bbox[1] + inset, bbox[2] - inset, bbox[3] - inset)
    short_side = min(interior_bbox[2] - interior_bbox[0], interior_bbox[3] - interior_bbox[1])
    interior_radius = int(short_side * INTERIOR_RADIUS_RATIO)
    print(f"Source: {w}x{h}  bbox={bbox}  interior_bbox={interior_bbox}  r={interior_radius}")

    interior_mask = build_rounded_mask((w, h), interior_bbox, interior_radius)
    chroma_alpha = build_chroma_alpha(src)
    final_alpha = ImageChops.lighter(interior_mask, chroma_alpha)

    out = src.convert("RGBA")
    out.putalpha(final_alpha)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUTPUT, "PNG")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
