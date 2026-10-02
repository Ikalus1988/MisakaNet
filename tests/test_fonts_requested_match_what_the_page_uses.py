#!/usr/bin/env python3
"""Ask Google Fonts for the weights this page uses — no more, and no fewer.

Measured on 2026-10-02, in Chromium, by collecting the computed `font-family`/`font-weight` of every
element with text on `docs/index.html`:

    Inter 400 (235 elements) · JetBrains Mono 400 (46) · Inter 700 (33) · JetBrains Mono 700 (14)
    JetBrains Mono 600 (11) · Inter 600 (8) · Orbitron 700 (4) · Orbitron 900 (1) · Ma Shan Zheng (1)

Two directions, both worth a rule:

* **No more.** The request asked for `Inter 300;900` and `Orbitron 400` and `Noto Sans SC 300`, none of
  which the page ever applies (`font-weight:300` does not occur at all). Each unused weight multiplies
  the stylesheet — and for `Noto Sans SC` a weight carries ~100 `unicode-range` subsets — so the file
  Google served was **577,542 bytes with 553 `@font-face` rules**, in the critical path, for glyphs the
  page never asks for. Requesting the used set brings it to **462,761 bytes / 444 rules**.
* **No fewer.** `Orbitron 800` and `JetBrains Mono 600` are applied by this page but were **not**
  requested, so the browser synthesised them from neighbouring weights. Adding them costs 2,893 bytes —
  measured — and removes the fake.

`Noto Sans SC 500` is kept although the measurement did not attribute it to an element: an inline style
in the search results (`font-weight:500` on a lesson title) can render CJK, and a CJK glyph at 500 would
otherwise be synthesised. When the page's styles change, re-measure with the snippet in the docstring of
this file rather than editing the table by hand.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGE = (REPO / "docs" / "index.html").read_text(encoding="utf-8")

#: family -> the weights the page applies. Re-measure, do not guess:
#:
#:     python3 - <<'PY'
#:     from playwright.sync_api import sync_playwright
#:     # serve docs/ locally, open it, then:
#:     #   [...document.querySelectorAll('body *')].forEach(el => { ... getComputedStyle ... })
#:     PY
EXPECTED = {
    # 400 is here because of an element that *inherits* it: `.modal-title` declares Orbitron and no
    # font-weight, so it renders at the body's 400. A review caught its removal with a pixel control —
    # forcing `.modal-title{font-weight:700}` on the old version produced a screenshot identical to the
    # new version's natural render, i.e. the title had silently moved to the 700 face.
    "Orbitron": ["400", "700", "800", "900"],
    "Ma Shan Zheng": None,          # a single weight, no axis in the URL
    "Inter": ["400", "500", "600", "700"],
    "Noto Sans SC": ["400", "500", "700"],
    "JetBrains Mono": ["400", "600", "700"],
}


def requested() -> dict[str, list[str] | None]:
    url = re.search(r"https://fonts\.googleapis\.com/css2\?([^\"']+)", PAGE)
    assert url, "the Google Fonts stylesheet is gone; this rule needs updating"
    out: dict[str, list[str] | None] = {}
    for part in url.group(1).split("&"):
        if not part.startswith("family="):
            continue
        name, _, axis = part[len("family="):].partition(":wght@")
        out[name.replace("+", " ")] = axis.split(";") if axis else None
    return out


def test_the_request_carries_exactly_the_weights_the_page_uses():
    got = requested()
    assert got == EXPECTED, (
        "the font request and the weights this page applies have drifted apart.\n"
        f"  requested: {got}\n  expected:  {EXPECTED}\n"
        "Unused weights inflate a 460 KB stylesheet in the critical path; missing ones make the browser "
        "synthesise a weight. Re-measure with the snippet in this file's docstring before editing.")


def _weights_the_page_declares() -> set[str]:
    """Every `font-weight` value in the page's own CSS and inline styles."""
    return set(re.findall(r"font-weight:\s*(\d{3})", PAGE))


def test_no_declared_weight_is_missing_from_the_request():
    """The direction that a URL-only rule misses, and the one this pull request got wrong first.

    The review that found the Orbitron regression also showed the failure mode of the rule above: it
    reads one URL string, so adding `font-weight:300` to the page's CSS (a weight nobody requests) leaves
    it green. This compares the declared weights against the requested ones. It is a *union* check —
    family-level correctness (which family needs which weight) is a browser question, and the review's
    pixel control is the only thing that answered it the first time.
    """
    requested_weights = {w for weights in requested().values() if weights for w in weights}
    declared = _weights_the_page_declares()
    missing = sorted(declared - requested_weights)
    assert not missing, (
        f"the page declares font-weight {missing}, which no requested family carries — the browser will "
        "synthesise it. Add the weight to the family that needs it (measure first), or stop declaring it.")


def test_the_stylesheet_is_still_one_request_with_swap():
    """`display=swap` is what keeps text visible while the faces load; `&`-splitting above depends on the
    single-link shape, so both are pinned here rather than assumed."""
    assert "display=swap" in PAGE, "without display=swap the page paints no text until the faces arrive"
    assert PAGE.count("fonts.googleapis.com/css2") == 1, "more than one font stylesheet request"
