#!/usr/bin/env python3
"""Generate the site's favicon from the repository's own avatar art.

Why this exists as a script rather than a checked-in binary: the icon is *derived* from
`docs/assets/misaka-avatar-crop.png`, and a derived asset whose derivation is not written down cannot be
re-derived when the source changes — it becomes a file nobody can update. The test next to this
(`tests/test_site_favicon.py`) holds the properties that matter (it exists, it is a real ICO, it carries a
16 px and a 32 px image, and it is small enough to fetch on every page load).

What it fixes, measured 2026-09-25: **`/favicon.ico` answered 404** — the zone's own status table showed
~15 requests/hour of it, and it was the only 4xx in that table that was ours rather than a WordPress
scanner's. No page declared `<link rel="icon">` either, so every browser fell back to requesting
`/favicon.ico` on every page load, of every page: about 360 self-inflicted 404s a day, which is exactly
the kind of noise that makes a real 404 harder to notice.

Usage::

    python3 scripts/build_favicon.py            # write docs/favicon.ico + docs/assets/favicon-32.png

The crop: the source is a 360x485 portrait, so a square favicon has to choose. `centering=(0.5, 0.3)`
takes the horizontal middle and slightly above centre, which is where a portrait's subject usually is —
and it is the one judgement here that a person can review by looking at the result. If the project gets a
purpose-drawn icon later, replace the source image and re-run this; nothing else has to change.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SOURCE = REPO / "docs" / "assets" / "misaka-avatar-crop.png"
ICO = REPO / "docs" / "favicon.ico"
PNG32 = REPO / "docs" / "assets" / "favicon-32.png"

# The sizes an ICO should carry: 16 for a tab, 32 for a bookmark/high-DPI tab, 48 for the desktop.
ICO_SIZES = [(16, 16), (32, 32), (48, 48)]
CROP_CENTRE = (0.5, 0.3)


def build() -> tuple[pathlib.Path, pathlib.Path]:
    try:
        from PIL import Image, ImageOps
    except ImportError:  # pragma: no cover - the tests assert the files instead
        sys.exit("Pillow is required to regenerate the favicon: pip install Pillow")

    if not SOURCE.is_file():
        sys.exit(f"the source image is gone: {SOURCE}")
    source = Image.open(SOURCE).convert("RGBA")
    # One square, cropped once and resized for every target, so all sizes agree on the framing.
    square = ImageOps.fit(source, (max(w for w, _ in ICO_SIZES),) * 2, method=Image.LANCZOS,
                          centering=CROP_CENTRE)

    ICO.parent.mkdir(parents=True, exist_ok=True)
    PNG32.parent.mkdir(parents=True, exist_ok=True)
    square.save(ICO, format="ICO", sizes=ICO_SIZES)
    square.resize((32, 32), Image.LANCZOS).save(PNG32, format="PNG", optimize=True)
    return ICO, PNG32


def main() -> int:
    ico, png = build()
    for path in (ico, png):
        print(f"wrote {path.relative_to(REPO)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
