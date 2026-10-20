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


# ── batch X: the three things it owns ─────────────────────────────────────────────────────────
# Each of these is a gate that must be able to fail. A gate that cannot fail is a comment.


def _page_with(tmp_path, css: str, name: str = "example.html"):
    """A one-page tree the gate can be run against."""
    page = tmp_path / "docs" / name
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"<style>\n{css}\n</style>\n", encoding="utf-8")
    return tmp_path


def test_a_side_colour_bar_is_a_violation(tmp_path):
    root = _page_with(tmp_path, "  .card { border-left: 3px solid #d29922; }")
    problems = cdc.check(root)
    assert any("side colour bar" in p for p in problems), problems


def test_a_zero_offset_glow_outside_the_brand_layer_is_a_violation(tmp_path):
    root = _page_with(tmp_path, "  .card { box-shadow: 0 0 20px rgba(0,229,255,0.4); }")
    problems = cdc.check(root)
    assert any("zero-offset glow" in p for p in problems), problems


def test_a_text_halo_outside_the_brand_layer_is_a_violation(tmp_path):
    root = _page_with(tmp_path, "  .title { text-shadow: 0 0 12px rgba(0,229,255,0.3); }")
    problems = cdc.check(root)
    assert any("zero-offset glow" in p for p in problems), problems


def test_the_purple_is_a_violation(tmp_path):
    root = _page_with(tmp_path, "  .badge { color: #a855f7; }")
    problems = cdc.check(root)
    assert any("purple" in p for p in problems), problems


def test_a_glow_in_an_inline_style_is_a_violation(tmp_path):
    """An inline style has no selector, so it cannot be the brand layer.

    The homepage's search button carried its halo in a `style="…"` attribute — the stylesheet
    had already given it up, and the page went on glowing. The gate reads the attributes too.
    """
    page = tmp_path / "docs" / "example.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        '<button style="box-shadow:0 0 14px rgba(0,229,255,0.16);">Search</button>\n',
        encoding="utf-8",
    )
    problems = cdc.check(tmp_path)
    assert any("inline style" in p for p in problems), problems


def test_the_journey_timeline_spine_is_not_a_side_bar():
    """The one written-down exception: a connector between steps, not an accent."""
    assert ("docs/journey/http-mcp/index.html", ".steps li") in cdc.SIDE_BAR_ALLOWLIST
    problems = cdc.check(REPO)
    assert not [p for p in problems if "side colour bar" in p], problems


def test_the_brand_layer_keeps_its_glow():
    """#3541 says the cyber signature is an asset. The gate must not make the homepage fail."""
    problems = cdc.check(REPO)
    assert not [p for p in problems if "zero-offset glow" in p], problems
    assert ".logo-title" in cdc.BRAND_GLOW_ALLOWLIST["docs/index.html"]


def test_the_brand_allowance_is_per_property_not_a_passport(tmp_path):
    """A logo may carry a text halo; a box shadow on the same rule is not the brand layer."""
    assert cdc.BRAND_GLOW_ALLOWLIST["docs/index.html"][".logo-title"] == {"text-shadow"}
    root = _page_with(tmp_path, "  .logo-title { box-shadow: 0 0 30px rgba(0,229,255,0.4); }",
                      name="index.html")
    problems = cdc.check(root)
    assert any("zero-offset glow" in p for p in problems), problems


def _markup_page(tmp_path, markup: str):
    """A one-page tree whose *body* is this markup (not CSS: `_page_with` puts its argument in a
    `<style>` block, which is the opposite of what these three tests need)."""
    page = tmp_path / "docs" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(markup, encoding="utf-8")
    return page


def test_the_emoji_count_reads_the_markup_not_the_stylesheet(tmp_path):
    """The first version of the report counted the CSS and found none — because the emoji are
    in the text. A count that says "0" on a page full of emoji is worse than no count."""
    page = _markup_page(tmp_path, "<p>hello</p>")
    assert cdc.emoji_occurrences(page) == []
    page = _markup_page(tmp_path, "<p>hello 🚀</p>")
    found = cdc.emoji_occurrences(page)
    assert [char for _line, _text, char in found] == ["🚀"]
    assert all(char not in cdc.TEXT_SYMBOLS for _line, _text, char in found)


def test_an_emoji_written_by_a_script_is_counted(tmp_path):
    """A script that writes `<div class="icon">💡</div>` puts an emoji on the page.

    The string literal inside a `<script>` is kept, because it is what the script writes into the
    document; only the script's *comments* are dropped.
    """
    page = _markup_page(tmp_path, "<script>card.innerHTML = '<div class=\"icon\">💡</div>';</script>")
    found = cdc.emoji_occurrences(page)
    assert "💡" in [char for _line, _text, char in found]


def test_an_emoji_in_a_javascript_comment_is_not_counted(tmp_path):
    """A comment is not on the page. The homepage's own comment quotes the old icon change
    ("⏳ → ✅"), and counting it would keep a pictograph in the codebase for no reason."""
    page = _markup_page(tmp_path, "<script>\n// Update UI: ⏳ → ✅\n</script>")
    assert cdc.emoji_occurrences(page) == []


def test_the_site_has_no_emoji_icons():
    """Batch Y: the site's icons are Lucide SVG, and the gate says so."""
    problems = [p for p in cdc.check(REPO) if "pictograph" in p]
    assert problems == [], "\n".join(problems)


def test_a_pictograph_in_a_page_fails_the_gate(tmp_path):
    """The control: a gate that cannot go red is a gate that proves nothing."""
    root = tmp_path
    (root / "docs").mkdir()
    (root / "docs" / "index.html").write_text("<p>🚀</p>", encoding="utf-8")
    problems = cdc.check(root)
    assert any("pictograph" in p for p in problems), problems


def test_every_inline_icon_is_one_of_the_ours():
    """A hand-drawn path is a path nobody can review — the icon set is the reviewable thing."""
    for asset in cdc.site_assets(REPO):
        rel = asset.relative_to(REPO).as_posix()
        unknown = cdc.unknown_icons(asset.read_text(encoding="utf-8", errors="replace"))
        assert not unknown, f"{rel}: an icon is not in scripts/site_icons.py — {unknown[:1]}"


def test_a_hand_drawn_icon_fails_the_gate(tmp_path):
    """The control for the icon check."""
    root = tmp_path
    (root / "docs").mkdir()
    (root / "docs" / "index.html").write_text(
        '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M1 2 L3 4 Z"/></svg>',
        encoding="utf-8")
    problems = cdc.check(root)
    assert any("not in scripts/site_icons.py" in p for p in problems), problems


def test_every_allowlisted_pictograph_says_why():
    """An exception without a reason is a hole nobody is watching."""
    for rel, entries in cdc.EMOJI_ALLOWLIST.items():
        for snippet, reason in entries:
            assert reason.strip(), f"{rel}: {snippet!r} has no reason"
            assert len(reason) > 40, f"{rel}: {snippet!r} has a token reason, not a reason"


def test_an_allowlist_entry_that_matches_nothing_is_a_hole():
    """An allowance nobody uses is a permission nobody granted: it would let the *next* pictograph
    of that shape in, silently."""
    for rel, entries in cdc.EMOJI_ALLOWLIST.items():
        asset = REPO / rel
        text = cdc.visible_text(asset)
        for snippet, _reason in entries:
            assert snippet in text, f"{rel}: the allowance {snippet!r} matches nothing any more"

