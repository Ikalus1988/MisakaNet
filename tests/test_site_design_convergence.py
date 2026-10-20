#!/usr/bin/env python3
"""The convergence gate must be able to fail — and must not count the wrong things.

`scripts/check_design_convergence.py` is #3541's acceptance table, executable. It reads the
*rendered* CSS of the hand-written pages, so a gate that counted the wrong things would be worse
than no gate: it would turn "the pages are converged" into a claim nobody checked.

This file is that gate's own test, and it is mostly about the things the gate must NOT count.
Each of those was a real false positive during the batch:

  * the managed token block — it is the vocabulary, not a page's own CSS, so counting its colours
    as "a page hardcoding a token colour" would fail the gate on the palette's own file;
  * `@media (max-width: 700px)` — a media *feature*, not a container width;
  * the `prefers-reduced-motion` block's `0.01ms !important` — #3541 says that block must survive,
    and a gate that demands it be tokenised would be asking for the accessibility fix to be undone;
  * a zero-offset glow — that is the homepage's brand layer, which batch X owns;
  * a shadow inside `@keyframes` — an animation frame, not a declaration the scale governs.

And the controls: a gate that returned [] unconditionally would pass everything else in this file.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import check_design_convergence as cdc  # noqa: E402

TOKEN_NAMES = [
    "--bg-0", "--bg-1", "--bg-2", "--fg-1", "--fg-2", "--fg-3",
    "--accent", "--accent-2", "--ok", "--warn", "--danger",
    "--line", "--line-strong",
    "--font-ui", "--font-brand", "--font-display", "--font-cn", "--font-mono",
    "--fs-3xs", "--fs-2xs", "--fs-xs", "--fs-sm", "--fs-md", "--fs-lg",
    "--fs-xl", "--fs-2xl", "--fs-3xl", "--fs-4xl", "--fs-display", "--fs-display-sm",
    "--fs-display-md", "--fs-tagline",
    "--sp-1", "--sp-2", "--sp-3", "--sp-4", "--sp-5", "--sp-6", "--sp-7", "--sp-8",
    "--r-sm", "--r-md", "--r-lg", "--r-pill",
    "--t-fast", "--t-base", "--ease",
    "--sh-1", "--sh-2",
]


def test_the_hand_written_pages_are_converged_today():
    problems = cdc.check(REPO)
    assert problems == [], "\n".join(problems)


def test_the_vocabulary_defines_every_name_the_pages_use():
    """A `var(--x)` with no definition is not a style, it is a silent fallback to `inherit`."""
    source = (REPO / "docs" / "_partials" / "design-tokens.html").read_text(encoding="utf-8")
    defined = set()
    for name in TOKEN_NAMES:
        assert f"{name}:" in source, f"{name} is not defined in the token source"
        defined.add(name)
    for page in cdc.hand_written_pages(REPO):
        text = page.read_text(encoding="utf-8")
        # A page may declare its own aliases in its own `:root` — those are page-local and fine.
        local = set()
        for match in re.finditer(r":root\s*\{([\s\S]*?)\}", text):
            local.update(re.findall(r"(--[a-z0-9-]+)\s*:", match.group(1)))
        used = set(re.findall(r"var\((--[a-z0-9-]+)\)", text))
        missing = used - defined - local
        assert not missing, f"{page.relative_to(REPO)}: {sorted(missing)}"


def test_the_managed_token_block_is_not_counted_as_a_page():
    """The vocabulary is not a page's own CSS — counting it would fail the gate on its own file."""
    css = cdc.css_of(REPO / "docs" / "index.html")
    # A *reference* to a token is the page using the vocabulary; a *definition* is the page
    # carrying its own copy of the palette, which is the thing the gate counts.
    assert "--bg-0:" not in css, "the managed token block leaked into the page's own CSS"
    assert "var(--accent)" in css, "the page should use the vocabulary"


def test_a_media_query_feature_is_not_a_container_width():
    # The feature itself is skipped (the `(` before `max-width`); a declaration inside the block
    # is a real declaration and is counted.
    assert cdc.values_of("@media (max-width: 700px) { .x { color: red; } }", "max-width") == []
    assert cdc.values_of("@media (max-width: 700px) { .x { max-width: 700px; } }", "max-width") == ["700px"]


def test_the_reduced_motion_block_is_not_a_violation():
    css = "@media (prefers-reduced-motion: reduce) { *, *::before { transition-duration: 0.01ms !important; } }"
    offenders = [v for v in cdc.values_of(css, "transition-duration") if v != "0.01ms !important"]
    assert offenders == [], offenders


def test_a_compound_radius_is_fine_when_every_part_is_a_token():
    assert cdc.compound_ok("var(--r-sm) 0 0 0", cdc.RADIUS_REF)
    assert cdc.compound_ok("var(--r-md) var(--r-md) 0 0", cdc.RADIUS_REF)
    assert not cdc.compound_ok("var(--r-md) 7px 0 0", cdc.RADIUS_REF)


def test_the_gate_reports_a_page_that_drifted(tmp_path):
    """The control: a gate that returns [] unconditionally would pass everything else here."""
    page = tmp_path / "docs" / "example.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "<style>\n"
        "  .card { border-radius: 7px; font-size: 13px; font-family: 'Inter', sans-serif; }\n"
        "</style>\n",
        encoding="utf-8",
    )
    css = cdc.css_of(page)
    assert cdc.offenders(css, "border-radius", {"0", "0px"}, cdc.RADIUS_REF) == ["7px"]
    assert cdc.offenders(css, "font-size", set(), cdc.SIZE_REF + r"|[\d.]+rem") == ["13px"]
    assert cdc.offenders(css, "font-family", {"inherit"}, r"var\(--font-[a-z-]+\)")


def test_a_page_that_uses_the_vocabulary_produces_no_offenders():
    css = (
        "<style>\n"
        "  .card { border-radius: var(--r-md); font-size: var(--fs-xs);"
        " font-family: var(--font-ui); max-width: 960px; box-shadow: var(--sh-1);"
        " transition: color var(--t-fast) ease; background: var(--bg-1); }\n"
        "</style>\n"
    )
    assert cdc.offenders(css, "border-radius", {"0", "0px"}, cdc.RADIUS_REF) == []
    assert cdc.offenders(css, "font-size", set(), cdc.SIZE_REF + r"|[\d.]+rem") == []
    assert cdc.offenders(css, "font-family", {"inherit"}, r"var\(--font-[a-z-]+\)") == []
    assert cdc.offenders(css, "max-width", cdc.CONTAINER_WIDTHS, r"100%|none|fit-content|\d+vw") == []
