#!/usr/bin/env python3
"""Every page load must not end in a 404 for the site's own icon.

Measured 2026-09-25 from the zone's status table: `/favicon.ico` was the **only** 4xx in that table that
was ours rather than a WordPress vulnerability scanner's — ~15 requests an hour, because no page declared
an icon and browsers therefore request `/favicon.ico` by default on every page load, of every page. The
file did not exist.

So this pins three things, and the third is the one that is easy to get wrong: the icon has to be small.
It is fetched on *every* page load, and this repository already has a 1.26 MB `data/lessons.json` riding
on every homepage visit — an icon is not the place to repeat that.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"
ICO = REPO / "docs" / "favicon.ico"
PNG32 = REPO / "docs" / "assets" / "favicon-32.png"

# A favicon is fetched before anything else on the page is rendered; 64 KB is generous for a 48px icon.
MAX_BYTES = 64 * 1024


def ico_entries(data: bytes) -> list[tuple[int, int, int]]:
    """(width, height, byte_size) per image in an ICO/cur container."""
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert reserved == 0 and kind == 1, f"not an ICO: reserved={reserved} type={kind}"
    entries = []
    for index in range(count):
        w, h, _colors, _r, _planes, _bpp, size, _offset = struct.unpack(
            "<BBBBHHII", data[6 + index * 16:22 + index * 16])
        entries.append((w or 256, h or 256, size))
    return entries


def test_the_default_icon_path_resolves():
    """`/favicon.ico` is what a browser asks for when a page does not say otherwise — including on the
    pages that are generated rather than hand-written, which is why the file at the site root is the fix
    and the `<link>` tags are the nicety."""
    assert ICO.is_file(), (
        "docs/favicon.ico is missing. Every page that does not declare an icon makes the browser request "
        "it, so this is one 404 per page load"
    )


def test_the_icon_is_a_real_multi_size_ico():
    entries = ico_entries(ICO.read_bytes())
    sizes = {(w, h) for w, h, _ in entries}
    assert (16, 16) in sizes, f"no 16x16 image (a tab bar is where this is most visible): {sorted(sizes)}"
    assert (32, 32) in sizes, f"no 32x32 image (high-DPI tabs and bookmarks): {sorted(sizes)}"
    assert all(w == h for w, h, _ in entries), f"a non-square favicon image: {entries}"


def test_the_icon_carries_no_more_than_it_needs():
    """Fetched on every page load — the size is a budget, not a detail."""
    for path in (ICO, PNG32):
        assert path.is_file(), f"{path.name} is missing"
        size = path.stat().st_size
        assert size <= MAX_BYTES, (
            f"{path.relative_to(REPO)} is {size} bytes; an icon is fetched on every page load and this "
            f"repository already ships 1.26 MB of lessons.json on the homepage"
        )


def test_the_homepage_names_the_icon():
    """Not required for the 404 to stop, but it decides *which* icon is used instead of leaving it to
    the user agent's guess.

    Parsed from the markup with comments stripped, not searched as text: the comment above those links
    explains the 404 in terms of `/favicon.ico`, so a substring search is satisfied by the explanation
    of the thing it is checking for — the first version of this test passed with the `<link>` deleted.
    """
    page = re.sub(r"<!--.*?-->", "", INDEX.read_text(encoding="utf-8"), flags=re.S)
    links = re.findall(r'<link[^>]*rel="icon"[^>]*>', page)
    assert links, "the homepage declares no icon link"
    hrefs = " ".join(links)
    assert "/favicon.ico" in hrefs, f"no icon link points at the file the default path serves: {links}"
    assert "/assets/favicon-32.png" in hrefs, f"no icon link offers the PNG: {links}"


def test_the_png_is_a_png():
    assert PNG32.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "favicon-32.png is not a PNG"


def test_the_generator_exists_so_the_icon_can_be_re_derived():
    """A derived binary whose derivation is not written down cannot be updated with its source."""
    generator = REPO / "scripts" / "build_favicon.py"
    assert generator.is_file(), "the favicon generator is gone; the icon can no longer be re-derived"
    text = generator.read_text(encoding="utf-8")
    assert "misaka-avatar-crop.png" in text, "the generator no longer names its source image"
