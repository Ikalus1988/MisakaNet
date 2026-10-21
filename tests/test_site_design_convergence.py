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



# ── batch Z: the cross-page colour, the page background and the footer shell ────────────────────
# Each of these is a gate that must be able to fail. The gate reads the *page*, not just its
# stylesheets, because three of the colours it is after were written by scripts.


def test_a_second_primary_colour_is_a_violation(tmp_path):
    """GitHub's blue was the second product's own primary, and it was on thirteen pages."""
    root = _page_with(tmp_path, "  .link { color: #58a6ff; }")
    problems = cdc.check(root)
    assert any("second primary colour" in p for p in problems), problems


def test_a_violet_is_a_violation_even_when_no_list_names_it(tmp_path):
    """The list of seven purples missed `#bc8cff` and `#d2a8ff`, and the report said "0 处" while
    three violets were still on the site. The gate classifies by hue now, so a violet nobody wrote
    down is still a violet."""
    root = _page_with(tmp_path, "  .badge { color: #bc8cff; }")
    problems = cdc.check(root)
    assert any("is a violet" in p for p in problems), problems


def test_a_light_lavender_is_a_violet(tmp_path):
    """`#d2a8ff` was on two pages and the accent band's own saturation floor of 0.45 let it walk
    past — a pale violet is still a violet, so the violet band has its own, lower floor."""
    root = _page_with(tmp_path, "  .badge { color: #d2a8ff; }")
    problems = cdc.check(root)
    assert any("is a violet" in p for p in problems), problems


def test_a_grey_that_happens_to_have_a_violet_hue_is_not_a_violet(tmp_path):
    """The violet band's floor exists so that a grey with a violet hue is a grey."""
    root = _page_with(tmp_path, "  .a { color: #9c9aa5; } .b { color: #b9b3c2; }")
    problems = cdc.check(root)
    assert not any("is a violet" in p for p in problems), problems


def test_the_greys_are_not_primary_colours(tmp_path):
    """The pages are full of near-greys with a blue hue. They are greys, and a gate that swept
    them in would report a site that does not exist."""
    root = _page_with(
        tmp_path,
        "  .a { color: #8b949e; } .b { color: #c9d1d9; } .c { border: 1px solid #30363d; }",
    )
    problems = cdc.check(root)
    assert not any("second primary colour" in p for p in problems), problems
    assert not any("is a violet" in p for p in problems), problems


def test_the_dark_navy_surfaces_are_not_primary_colours(tmp_path):
    """`#0f172a` and `#1f3a5f` are navy, not blue: they are dark enough that the value floor has
    to keep them out of the band."""
    root = _page_with(tmp_path, "  .a { background: #0f172a; } .b { background: #1f3a5f; }")
    problems = cdc.check(root)
    assert not any("second primary colour" in p for p in problems), problems


def test_the_vocabulary_accents_are_not_in_the_band(tmp_path):
    """The site's two accents are the vocabulary's cyan and magenta — they are what the band is
    defined *around*."""
    root = _page_with(tmp_path, "  .a { color: #00e5ff; } .b { color: #ff0080; }")
    problems = cdc.check(root)
    assert not any("second primary colour" in p for p in problems), problems
    assert not any("is a violet" in p for p in problems), problems


def test_a_page_background_that_is_not_the_vocabulary_is_a_violation(tmp_path):
    root = _page_with(tmp_path, "  body { background: #0d1117; }")
    problems = cdc.check(root)
    assert any("page background" in p for p in problems), problems


def test_a_glow_over_the_vocabulary_background_is_the_vocabulary_background(tmp_path):
    """The search page paints a radial gradient over `--bg-0`; the base is still `--bg-0`, and
    the base is the last layer of the shorthand."""
    root = _page_with(
        tmp_path,
        "  body { background: radial-gradient(circle at 50% -20%, rgba(0,229,255,0.09),"
        " transparent 38%), var(--bg-0); }",
    )
    problems = cdc.check(root)
    assert not any("page background" in p for p in problems), problems


def test_a_page_without_a_footer_is_a_violation(tmp_path):
    """The footer is the only navigation every page shares; a page without one is a page the
    reader cannot leave."""
    root = _page_with(tmp_path, "  body { background: var(--bg-0); }")
    problems = cdc.check(root)
    assert any("no footer" in p for p in problems), problems


def test_a_page_that_defines_its_own_footer_shell_is_a_violation(tmp_path):
    """The shell lives in the shared token block. A page that spells its own is the second
    spelling of the same shell, which is how six shells became fourteen."""
    root = _page_with(
        tmp_path,
        "  body { background: var(--bg-0); }\n"
        "  .footer { margin-top: 2.5rem; color: #8b949e; }",
    )
    problems = cdc.check(root)
    assert any("footer shell" in p for p in problems), problems


def test_the_shared_block_owns_the_footer_shell():
    """If the rule is deleted from the block, every page loses the shell with it — and
    `sync_design_tokens.py --check` stays green, because the pages still agree with the block.
    They just agree on nothing."""
    source = (REPO / "docs" / "_partials" / "design-tokens.html").read_text(encoding="utf-8")
    assert re.search(r"^\s*\.footer\s*\{", source, re.MULTILINE), (
        "the shared token block no longer owns the footer shell")


def test_no_page_carries_its_own_footer_shell():
    for page in cdc.hand_written_pages(REPO):
        for scope, selector, _body in cdc.scoped_rules(cdc.css_of(page)):
            if scope is not None:
                continue
            assert not any(part.strip() in (".footer", "footer") for part in selector.split(",")), (
                f"{page.relative_to(REPO)}: the page defines its own footer shell")


def test_every_hand_written_page_carries_the_footer_and_the_link_row():
    for page in cdc.hand_written_pages(REPO):
        rel = page.relative_to(REPO).as_posix()
        if rel in cdc.NOT_A_PAGE:
            continue
        text = page.read_text(encoding="utf-8")
        assert '<footer class="footer">' in text, f"{rel}: no footer shell"
        assert "site-links:start" in text, f"{rel}: no site-links row"


def test_every_accent_band_allowlist_entry_says_why():
    """An exception without a reason is a hole nobody is watching."""
    for (rel, colour), reason in cdc.ACCENT_BAND_ALLOWLIST.items():
        assert reason.strip(), f"{rel}: {colour} has no reason"
        assert len(reason) > 40, f"{rel}: {colour} has a token reason, not a reason"


def test_an_accent_band_allowlist_entry_that_matches_nothing_is_a_hole():
    """An allowance nobody uses is a permission nobody granted: it would let the *next* colour of
    that shape in, silently."""
    for (rel, colour) in cdc.ACCENT_BAND_ALLOWLIST:
        page = REPO / rel
        used = {cdc.colour_rgb(literal) for _lineno, literal in cdc.colour_occurrences(page)}
        assert colour in used, f"{rel}: the allowance {colour} matches nothing any more"


def test_the_allowlist_is_keyed_on_the_colour_and_not_on_the_spelling():
    """`#3b82f6` and `rgba(59,130,246,0.14)` are one colour, and an allowlist keyed on the string
    would allow the hex and silently forbid the rgba. The gate has to see the badge's own
    background as the badge."""
    assert cdc.accent_band_allowed("docs/search/index.html", "#3b82f6")
    assert cdc.accent_band_allowed("docs/search/index.html", "rgba(59,130,246,0.14)")
    assert cdc.accent_band_allowed("docs/search/index.html", "#3B82F6")


def test_a_colour_with_an_alpha_channel_is_read():
    """`rgba(163,113,247,0.1)` used to be unparseable, and a colour the gate cannot parse is a
    colour the gate cannot forbid — which is how sixteen old GitHub blues and four violet tints
    survived every run."""
    assert cdc.colour_rgb("rgba(163,113,247,0.1)") == (163, 113, 247)
    assert cdc.colour_rgb("rgb(88,166,255)") == (88, 166, 255)
    hue, saturation, value = cdc.colour_hsv("rgba(163,113,247,0.1)")
    assert 250 <= hue <= 290 and saturation >= 0.45 and value >= 0.5


def test_a_transparent_violet_is_a_violation(tmp_path):
    """The alpha channel is not a hiding place: this is the gate that was blind to it."""
    root = _page_with(tmp_path, "  .badge { color: rgba(163,113,247,0.14); }")
    problems = cdc.check(root)
    assert any("is a violet" in p for p in problems), problems


def test_a_transparent_second_primary_is_a_violation(tmp_path):
    """GitHub's blue at 12% was on the pages all along, and the gate reported a clean tree."""
    root = _page_with(tmp_path, "  .link { color: rgba(88,166,255,0.12); }")
    problems = cdc.check(root)
    assert any("second primary colour" in p for p in problems), problems


def test_the_old_palette_is_all_caught_at_once(tmp_path):
    """The control for the whole batch: one page carrying the palette the batch removed — GitHub's
    blue, its transparent twin, a violet, a transparent violet — must produce four complaints, not
    one. A gate that reports a clean tree here would have reported a clean tree on the real site."""
    root = _page_with(
        tmp_path,
        "  .a { color: #58a6ff; }"
        "  .b { color: rgba(88,166,255,0.12); }"
        "  .c { color: #bc8cff; }"
        "  .d { color: rgba(163,113,247,0.14); }",
    )
    problems = cdc.check(root)
    assert sum("second primary colour" in p for p in problems) == 2, problems
    assert sum("is a violet" in p for p in problems) == 2, problems
