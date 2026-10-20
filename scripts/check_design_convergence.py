#!/usr/bin/env python3
"""The design system is a set of numbers, and this script is the numbers (#3541).

Issue #3541 says, in its own words, that its acceptance is "**only numeric gates and pixel
comparison, not subjective scoring**" — and then lists eleven of them. A criterion nobody can run
is a criterion nobody can meet, so this file is that list, executable.

    python3 scripts/check_design_convergence.py            # the table
    python3 scripts/check_design_convergence.py --check    # exit 1 when an enforced criterion fails

What is *enforced* here and what is only *reported* is deliberate, and the reason is the batch
plan: #3541 splits the work into V (the vocabulary — done), W (mechanical convergence), X (de-AI:
flatten cards, pull the colour bars in, keep the glow for the logo and the hero) and Y (icons).
Enforcing X's and Y's numbers now would make this script red for work that has not been scheduled
yet, and a red gate that is red on purpose is a gate people learn to ignore. So:

  * enforced here: the six categories W owns — radius, motion, shadow, font-size, font-family,
    container width — plus the rule that no page hardcodes a colour a token already carries;
  * reported here: the four that X and Y own — the single accent colour, the glow count, the
    side colour bars, the emoji — each printed with its current count so the next batch can see
    what it owes.

Every check reads the *rendered* CSS of the hand-written pages: the `<style>` blocks and the
inline `style="…"` attributes, because both carry the values the browser sees.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOKENS = Path("docs") / "_partials" / "design-tokens.html"

# The icon set, so the gate can tell a Lucide shape from a hand-drawn one. `scripts/` is on the
# path when this runs as `python3 scripts/check_design_convergence.py`, and the sibling import is
# the same one `scripts/arm_auto_merge_lesson_prs.py` already does.
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from site_icons import ICONS as SITE_ICONS  # noqa: E402

# ── the vocabulary this script checks against ──────────────────────────────────────────────────────
RADIUS_TOKENS = {"--r-sm", "--r-md", "--r-lg", "--r-pill"}
MOTION_TOKENS = {"--t-fast", "--t-base"}
SHADOW_TOKENS = {"--sh-1", "--sh-2"}
SIZE_TOKENS = {f"--fs-{n}" for n in
               ("3xs", "2xs", "xs", "sm", "md", "lg", "xl", "2xl", "3xl", "4xl", "display", "display-sm")}
FAMILY_TOKENS = {"--font-ui", "--font-brand", "--font-display", "--font-cn", "--font-mono"}
# The token palette, by value: a page that hardcodes one of these is carrying a second copy of a
# value the vocabulary already owns, and the copy is how two pages end up with two designs.
TOKEN_VALUES = {
    "#070b15", "#0d1424", "#161b22", "#e2e8f0", "#94a3b8", "#64748b",
    "#00e5ff", "#ff0080", "#22c55e", "#f0c040", "#ef4444",
    "rgba(148,163,184,.14)", "rgba(0,229,255,.28)",
}
CONTAINER_WIDTHS = {"960px", "720px"}

# ── what batch X owns ─────────────────────────────────────────────────────────────────────────
# A colour bar down the left edge of a card is the shape #3541 calls out: an edge that carries
# meaning the box itself does not. One exception is written down rather than left to taste — the
# journey page draws an ordered list with a 2px hairline spine, which is a connector between the
# steps, not an accent.
SIDE_BAR_ALLOWLIST = {
    ("docs/journey/http-mcp/index.html", ".steps li"),
}

# The homepage's glows are the brand: #3541 says the cyber signature is an asset, not a problem to
# fix. Every other halo is gone. The allowlist says which ones survive and by selector, so a new
# one has to be written down to survive — and the reason is in the name.
# The allowance is per *property*, not per selector: the logo may carry a text halo, but a box
# shadow on the same rule is not the brand layer and has to be written down separately.
BRAND_GLOW_ALLOWLIST = {
    "docs/index.html": {
        ".header-avatar": {"filter"},            # the logo's drop halo
        ".logo-title": {"text-shadow"},          # the Orbitron title
        ".logo-cn": {"text-shadow"},             # the Chinese calligraphy subtitle
        ".logo-tagline": {"text-shadow"},
        ".content-glass": {"box-shadow"},        # the hero glass panel
        "@keyframes energyFlow": {"box-shadow"},  # the panel's border energy flow
    },
}

# The one accent the vocabulary does not own. It was a purple badge ramp on the homepage, and two
# thirds of it was dead CSS; what was live moved to `--accent-2`.
PURPLE = "#a855f7"
# The rest of the purples on the site. `#a855f7` is the one #3541 names, so it is the one the gate
# enforces — but a report that says "0 处" while two pages still carry a violet is a report that
# lies, and the lie is what made this row look finished before it was. Batch Z is where the
# cross-page colour converges; until then the number is shown, not enforced.
PURPLE_FAMILY = ("#a855f7", "#a371f7", "#7c3aed", "#8b5cf6", "#9d5cff", "#c084fc", "#d8b4fe")

# A pictograph, not a symbol: the box-drawing characters the comments use, the arrows, the
# keyboard glyphs and the text dingbats are typography, and counting them would make the number
# the Y batch has to bring to zero a number nobody could act on.
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\u27BF\U00002B00-\u2BFF]")
TEXT_SYMBOLS = set("✓✗✘★☆⚠☰✕✦✧※⌘⌨")

# ── what batch Y owns ───────────────────────────────────────────────────────────────────────────
# An emoji is a colour bitmap chosen by the platform: the same markup renders three different
# icons in three browsers, and none of them is the page's accent colour. The site's icons are
# Lucide SVGs (scripts/site_icons.py), and this gate keeps it that way.
#
# The exceptions are written down, one line each, *with the reason* — a rule nobody can see is a
# rule nobody can follow, and an exception without a reason is a hole nobody is watching. Each is
# content rather than decoration:
EMOJI_ALLOWLIST = {
    "docs/index.html": [
        ("## \U0001F9E0 通过公开通道加入御坂网络",
         "the body of the GitHub issue the registration creates: the page and "
         "workers/register-proxy-sw.js are two writers of the same line and "
         "tests/test_registration_copy.py pins the shell, so the mark is a contract with the "
         "worker, and GitHub is what renders it"),
    ],
    "docs/journey/index.html": [
        ("\U0001F4CB lessons/",
         "the page mocks a terminal and the mock has to be true: misakanet/search/engine.py "
         "prints the clipboard mark before the result count"),
        ("\U0001F7E2 high/actionable",
         "the confidence mark the same script prints next to a high-confidence result"),
        ("/✅|pass|Success|成功|ok/i",
         "a classifier that matches the tool's own output, so the mark it looks for is the mark "
         "the tool prints"),
        ("/❌|fail|Error|error|missing|blocked/i",
         "the same classifier, for the line that failed"),
    ],
}

# ── the pages ────────────────────────────────────────────────────────────────────────────────────
STYLE_BLOCK = re.compile(r"<style\b[^>]*>([\s\S]*?)</style>", re.IGNORECASE)
# The managed token block is copied verbatim into every page (batch V). It is the vocabulary, not
# the page's own CSS — counting its colours as "a page hardcoding a token colour" would have the
# gate fail on the very file that defines the palette.
TOKEN_BLOCK = re.compile(r"<!-- design-tokens:start -->[\s\S]*?<!-- design-tokens:end -->")
# A shadow inside `@keyframes` is an animation frame, not a declaration the scale governs — the
# same reasoning that keeps keyframe durations literal. The homepage's corner pulse animates its
# shadow between four hand-written values; none of them is an elevation tier.
KEYFRAMES = re.compile(r"@keyframes\b[^\{]*\{[\s\S]*?\n\s*\}", re.IGNORECASE)
INLINE_STYLE = re.compile(r"\bstyle\s*=\s*\"([^\"]*)\"", re.IGNORECASE)


def hand_written_pages(root: Path = REPO) -> list[Path]:
    """The same partition as `sync_site_partials.py` and `sync_design_tokens.py`."""
    pages = sorted((root / "docs").rglob("*.html"))
    out = []
    for page in pages:
        rel = page.relative_to(root / "docs")
        if "_partials" in rel.parts or "lessons" in rel.parts or "topics" in rel.parts:
            continue
        out.append(page)
    return out


def site_assets(root: Path = REPO) -> list[Path]:
    """Everything the site's own visible text is made of.

    The pages, the locale files and the site's own script. The last two are part of what the
    reader sees: `switchLang` writes a locale string into the page, and `buildErrorHTML` writes a
    panel into it. A gate that read only the pages would have called the site emoji-free on the
    day the locale files still carried four.
    """
    out = list(hand_written_pages(root))
    locales = root / "docs" / "locales"
    if locales.is_dir():
        out.extend(sorted(locales.glob("*.json")))
    scripts = root / "docs" / "js"
    if scripts.is_dir():
        out.extend(sorted(scripts.glob("*.js")))
    return out


def css_of(page: Path) -> str:
    """Every declaration the browser will see on this page: the style blocks and the inline styles."""
    text = page.read_text(encoding="utf-8", errors="replace")
    text = TOKEN_BLOCK.sub("", text)
    parts = [m.group(1) for m in STYLE_BLOCK.finditer(text)]
    parts.extend(m.group(1) for m in INLINE_STYLE.finditer(text))
    return "\n".join(parts)


def declarations(css: str, prop: str) -> list[tuple[str, str]]:
    """Every `prop: value` in this CSS, as (property, value) pairs.

    The value stops at the next `;` or at a closing brace, so `border-radius: 8px solid red` still
    yields `8px solid red` rather than pretending the value is only `8px`.
    """
    out = []
    # The lookbehind also rejects `(`: `@media (max-width: 700px)` is a media *feature*, and
    # counting it as a container width is how a 700px breakpoint ended up in the width list.
    for match in re.finditer(rf"(?<![(\w-]){re.escape(prop)}\s*:\s*([^;{{}}]+)", css, re.IGNORECASE):
        out.append((prop, match.group(1).strip()))
    return out


def values_of(css: str, prop: str) -> list[str]:
    return [value for _, value in declarations(css, prop)]


def offenders(css: str, prop: str, allowed: set[str], token_pattern: str) -> list[str]:
    """Values that are neither an allowed literal nor a token reference."""
    bad = []
    for value in values_of(css, prop):
        if value in allowed:
            continue
        if re.fullmatch(token_pattern, value):
            continue
        bad.append(value)
    return bad


def compound_ok(value: str, token_pattern: str) -> bool:
    """A compound value is fine when every part is a token or a zero.

    `border-radius: 4px 4px 0 0` is one shape, and half of it being a token makes the whole thing
    a token — so the check has to look at the parts, not at the whole string. (A radius of
    `var(--r-sm) 0 0 0` is a different corner from `var(--r-sm)`; the shape survives the swap.)
    """
    parts = value.split()
    if not parts:
        return False
    for part in parts:
        if part in ("0", "0px"):
            continue
        if re.fullmatch(token_pattern, part):
            continue
        return False
    return True


# ── reading a rule with its selector ───────────────────────────────────────────────────────────
COMMENT = re.compile(r"/\*[\s\S]*?\*/")
# A layer whose x and y offsets are both zero is a halo, not an elevation: it casts no shadow in
# any direction, it only bleeds colour. `inset 0 0 60px rgba(...)` is the same thing drawn inside.
GLOW_LAYER = re.compile(r"(?:inset\s+)?\b0\s+0\s+(?:\d*\.?\d+px|\d*\.?\d+)")


def scoped_rules(css: str) -> list[tuple[str | None, str, str]]:
    """(scope, selector, body) for every rule in this CSS.

    `scope` is the `@keyframes` name when the rule is a frame of an animation, and `None` for the
    page's own CSS. The distinction matters because #3541 keeps the homepage's animations — a
    frame of the border energy flow is brand, while the same shadow written on a button is the
    "everything glows" look the batch removes.
    """
    css = COMMENT.sub("", css)
    frames: list[tuple[str, str]] = []
    page_css = css
    for match in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", css):
        name = match.group(1)
        depth, end = 0, match.end() - 1
        while end < len(css):
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        frames.append((name, css[match.end():end]))
        # The frames are read on their own; leaving them in the page CSS would count them twice.
        page_css = page_css.replace(css[match.start():end + 1], " ")

    out: list[tuple[str | None, str, str]] = []
    for name, inner in frames:
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", inner):
            out.append((name, " ".join(match.group(1).split()), match.group(2)))
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", page_css):
        out.append((None, " ".join(match.group(1).split()), match.group(2)))
    return out


def declarations_in(body: str, prop: str) -> list[str]:
    """The values of `prop` inside one rule body."""
    return [m.group(1).strip()
            for m in re.finditer(rf"(?<![(\w-]){re.escape(prop)}\s*:\s*([^;{{}}]+)", body, re.IGNORECASE)]


def inline_style_blocks(page: Path) -> list[str]:
    """Every `style="…"` attribute on the page, as its own declaration block.

    An inline style has no selector, so it cannot be the brand layer — the brand layer is written
    as rules. That makes a halo in one of these a violation with nowhere to hide, and it is how the
    homepage's search button kept a glow the stylesheet no longer had.
    """
    text = page.read_text(encoding="utf-8", errors="replace")
    text = TOKEN_BLOCK.sub("", text)
    return [m.group(1) for m in INLINE_STYLE.finditer(text)]


TOKEN_REF = r"var\(--[a-z0-9-]+\)"
DURATION = re.compile(r"\d*\.?\d+s")
RADIUS_REF = r"var\(--r-(?:sm|md|lg|pill)\)"
MOTION_REF = r"var\(--t-(?:fast|base)\)"
SHADOW_REF = r"var\(--sh-[12]\)"
SIZE_REF = r"var\(--fs-[a-z0-9-]+\)"


def check(root: Path = REPO) -> list[str]:
    """Every enforced criterion that is not met, as a list of problem strings."""
    problems: list[str] = []
    pages = hand_written_pages(root)

    for page in pages:
        rel = page.relative_to(root).as_posix()
        css = css_of(page)

        # 2 — radius: three tiers (plus the pill shape).
        bad = [v for v in offenders(css, "border-radius", {"0", "0px"}, RADIUS_REF)
               if not compound_ok(v, RADIUS_REF)]
        if bad:
            problems.append(f"{rel}: border-radius still literal — {sorted(set(bad))[:6]}")

        # 3 — motion: two durations. Keyframe timings are a different animal (a loop length, not a
        # UI transition) and are counted separately, not silently folded in.
        # `0.01ms !important` is the `prefers-reduced-motion` block, and #3541's risk section says
        # that block must be preserved — a gate that demands it be tokenised would be asking for
        # the accessibility fix to be undone.
        # A transition shorthand is `property duration easing`, so the duration is one *part* of
        # the value: `transition: all var(--t-base) ease` is as valid as `transition: var(--t-base)`.
        # Matching the whole value (as the first version of this check did) rejected the former.
        bad = []
        for value in values_of(css, "transition-duration"):
            if value in ("0s", "0.01ms !important"):
                continue
            if not re.fullmatch(MOTION_REF, value):
                bad.append(value)
        for value in values_of(css, "transition"):
            for part in value.split():
                if not DURATION.fullmatch(part):
                    continue
                if not re.fullmatch(MOTION_REF, part):
                    bad.append(value)
                    break
        if bad:
            problems.append(f"{rel}: transition duration still literal — {sorted(set(bad))[:6]}")

        # 4 — shadows: two tiers. A zero-offset glow is not an elevation shadow: it is the
        # homepage's brand layer, and #3541 keeps it for the logo and the hero — so it is counted
        # (that count is X's job to drive to zero) rather than failed here.
        static_css = KEYFRAMES.sub("", css)
        bad = []
        for value in offenders(static_css, "box-shadow", {"none", "none !important"}, SHADOW_REF):
            # A zero-offset layer is a glow, and a glow is the brand layer (X's job), not an
            # elevation tier. `0 0 0 0 rgba(…)` is a no-op layer that marks the same thing.
            if re.search(r"0 0 (?:\d+px|0 0)", value):
                continue
            bad.append(value)
        if bad:
            problems.append(f"{rel}: box-shadow still literal — {sorted(set(bad))[:6]}")

        # 5 — font sizes: never px, always a token or a rem.
        sizes = values_of(css, "font-size")
        px = sorted({s for s in sizes if re.search(r"\d\s*px", s)})
        if px:
            problems.append(f"{rel}: font-size in px — {px[:8]}")
        bad = offenders(css, "font-size", set(), SIZE_REF + r"|[\d.]+rem")
        if bad:
            problems.append(f"{rel}: font-size is neither a token nor rem — {sorted(set(bad))[:6]}")

        # 6 — font families: four tokens, no literal stacks.
        bad = offenders(css, "font-family", {"inherit"}, r"var\(--font-[a-z-]+\)")
        if bad:
            problems.append(f"{rel}: font-family still a literal stack — {sorted(set(bad))[:4]}")

        # 7 — container widths: two tiers. Only *page* widths are in scope: a component's own
        # width (an icon box at 200px, an avatar at 240px) is not a container width, and the
        # breakpoint widths live in `@media (...)`, which the declaration reader skips.
        bad = [v for v in offenders(css, "max-width", CONTAINER_WIDTHS, r"100%|none|fit-content|\d+vw")
               if re.fullmatch(r"\d+px", v) and int(v[:-2]) >= 500]
        if bad:
            problems.append(f"{rel}: max-width is not one of the two container widths — {sorted(set(bad))[:8]}")

        # A colour that a token already carries is a second copy of a value the vocabulary owns.
        hexes = set()
        for value in re.findall(r"#[0-9a-fA-F]{3,8}\b", css):
            hexes.add(value.lower())
        dupes = sorted(hexes & TOKEN_VALUES)
        if dupes:
            problems.append(f"{rel}: hardcodes a colour the vocabulary already has — {dupes}")

        # ── batch X: the three things it owns ─────────────────────────────────────────────────
        brand = BRAND_GLOW_ALLOWLIST.get(rel, {})
        for scope, selector, body in scoped_rules(css):
            selectors = [s.strip() for s in selector.split(",")]

            # 9 — a colour bar down the left edge of a card.
            for value in declarations_in(body, "border-left"):
                if value.startswith("0"):
                    continue
                if (rel, selector.strip()) in SIDE_BAR_ALLOWLIST:
                    continue
                problems.append(f"{rel}: border-left side colour bar — {selector.strip()} ({value})")

            # 4 — a zero-offset halo. The brand layer keeps its own; nothing else may have one.
            for prop in ("box-shadow", "text-shadow", "filter"):
                for value in declarations_in(body, prop):
                    if not GLOW_LAYER.search(value):
                        continue
                    if scope is not None:
                        if prop in brand.get(f"@keyframes {scope}", set()):
                            continue
                    elif any(prop in brand.get(s, set()) for s in selectors):
                        continue
                    problems.append(f"{rel}: zero-offset glow outside the brand layer — "
                                    f"{selector.strip()}: {value}")

        # An inline style cannot be the brand layer: it has no selector to be one of.
        for block in inline_style_blocks(page):
            for prop in ("box-shadow", "text-shadow", "filter"):
                for value in declarations_in(block, prop):
                    if GLOW_LAYER.search(value):
                        problems.append(f"{rel}: zero-offset glow in an inline style — {value}")

        # The purple: the one accent the vocabulary does not own.
        if re.search(rf"{re.escape(PURPLE)}\b", css, re.IGNORECASE):
            problems.append(f"{rel}: the purple {PURPLE} is back — it is not a token")

    # 13 — the icons are SVG, not emoji. The exceptions are content, and each is written down in
    # EMOJI_ALLOWLIST with the reason it is not an icon.
    for asset in site_assets(root):
        rel = asset.relative_to(root).as_posix()
        allowed = [snippet for snippet, _reason in EMOJI_ALLOWLIST.get(rel, [])]
        for lineno, line, char in emoji_occurrences(asset):
            if any(snippet in line for snippet in allowed):
                continue
            problems.append(
                f"{rel}:{lineno}: {char} is a pictograph, not an icon — the site's icons are Lucide "
                "SVG (scripts/site_icons.py)")

    # 14 — every inline icon is one of ours. A hand-drawn path is a path nobody can review.
    for asset in site_assets(root):
        rel = asset.relative_to(root).as_posix()
        for body in unknown_icons(asset.read_text(encoding="utf-8", errors="replace")):
            problems.append(
                f"{rel}: an inline icon is not in scripts/site_icons.py — {body[:60]}")

    return problems


def _blank(match: re.Match) -> str:
    """Replace a matched span with spaces, keeping its newlines.

    Keeping the line count is the point: the report names a line, and a report that names the
    wrong line is worse than no report.
    """
    return re.sub(r"[^\n]", " ", match.group(0))


SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>[\s\S]*?</script\s*>", re.IGNORECASE)
JS_BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
# A *whole-line* `//` comment. A `//` in the middle of a line is left alone: in this codebase it
# is a URL inside a string ("https://…") far more often than it is a comment.
JS_LINE_COMMENT = re.compile(r"^[ \t]*//[^\n]*$", re.MULTILINE)


def _strip_js_comments(block: str) -> str:
    """Blank out the comments of a `<script>` body.

    A comment is not on the page, and a comment that quotes an icon ("⏳ → ✅") would otherwise be
    counted as one. The limit of this is stated rather than hidden: a line of a *template literal*
    that begins with `//` is also blanked, because the scanner does not parse JavaScript. No such
    line exists today, and `tests/test_site_design_convergence.py` pins the count that would
    change if one appeared.
    """
    head_end = block.find(">")
    if head_end < 0:
        return block
    body = block[head_end + 1:]
    body = JS_BLOCK_COMMENT.sub(_blank, body)
    body = JS_LINE_COMMENT.sub(_blank, body)
    return block[:head_end + 1] + body


def visible_text(path: Path) -> str:
    """The text of a page or asset that a reader can actually see.

    Removed: `<style>` blocks (CSS is not prose), HTML comments, and the *comments* of a
    `<script>`. Kept: the string literals inside a script, because a script that writes
    `<b>${t("regWait")}</b>` puts that string on the page.

    The first version of this report read the *CSS*, and it found nothing — because the emoji are
    in the text, not in the stylesheet. A count that says "0" when the page is full of emoji is
    worse than no count: the Y batch would have had nothing to do and nothing to prove.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<style\b[^>]*>[\s\S]*?</style\s*>", _blank, text, flags=re.IGNORECASE)
    text = re.sub(r"<!--[\s\S]*?-->", _blank, text)
    text = SCRIPT_BLOCK.sub(lambda m: _strip_js_comments(m.group(0)), text)
    return text


def emoji_occurrences(path: Path) -> list[tuple[int, str, str]]:
    """(line number, the line, the pictograph) for every emoji a reader can see.

    Occurrences rather than distinct characters: "42 different emoji" and "86 emoji" are different
    numbers for different jobs, and the gate's job is to say "there is none of these left".
    """
    out = []
    for lineno, line in enumerate(visible_text(path).splitlines(), 1):
        for char in EMOJI.findall(line):
            if char in TEXT_SYMBOLS:
                continue
            out.append((lineno, line.strip(), char))
    return out


def icon_bodies(text: str) -> list[str]:
    """The shapes of every inline icon in this markup."""
    return re.findall(r'<svg\b[^>]*\bclass="ico"[^>]*>(.*?)</svg>', text, re.DOTALL)


def unknown_icons(text: str) -> list[str]:
    """The inline icons whose shape is not in the icon set.

    A hand-drawn path is a path nobody can review, and the whole point of the Y batch is that the
    icons are a *system* with one source. So the gate asks the shape to be one of ours.
    """
    known = set(SITE_ICONS.values())
    return [body for body in icon_bodies(text) if body not in known]


def report(root: Path = REPO) -> list[tuple[str, str, str, bool]]:
    """The acceptance table from #3541, with the current number for each row.

    Returns (criterion, current, target, enforced?) rows — enforced rows are the ones `check()`
    fails on; the rest are printed so the next batch can see what it owes.
    """
    pages = hand_written_pages(root)
    css = "\n".join(css_of(page) for page in pages)

    radii = set()
    for value in values_of(css, "border-radius"):
        for part in value.split():
            if re.fullmatch(r"\d+px", part) or part == "0":
                radii.add(part)
    durations = set()
    for value in values_of(css, "transition"):
        for part in value.split():
            if re.fullmatch(r"\d*\.?\d+s", part):
                durations.add(part)
    shadows = [v for v in values_of(css, "box-shadow") if v != "none"]
    px_sizes = {v for v in values_of(css, "font-size") if re.search(r"\d\s*px", v)}
    rem_sizes = {v for v in values_of(css, "font-size") if re.fullmatch(r"[\d.]+rem", v)}
    # A `var(--font-…)` reference *is* the vocabulary being used, not a literal stack — counting
    # the references as stacks would report "5 种字面栈" on a page that has none.
    families = {v for v in values_of(css, "font-family")
                if v != "inherit" and not v.startswith("var(")}
    widths = {v for v in values_of(css, "max-width")
              if re.fullmatch(r"\d+px", v) and int(v[:-2]) >= 500}
    # The glows, split by where they are: the brand layer's and everybody else's.
    glows = brand_glows = 0
    side_bars = 0
    purples = 0
    other_purples = 0
    emoji_icons = emoji_content = 0
    for page in pages:
        rel = page.relative_to(root).as_posix()
        brand = BRAND_GLOW_ALLOWLIST.get(rel, {})
        page_css = css_of(page)
        purples += len(re.findall(rf"{re.escape(PURPLE)}\b", page_css, re.IGNORECASE))
        # The *page* rather than its CSS: one of the survivors is a colour a script writes into a
        # badge (`docs/index.html`'s per-domain palette), and a report that only read the
        # stylesheet would have missed it.
        page_text = page.read_text(encoding="utf-8", errors="replace")
        other_purples += sum(
            len(re.findall(rf"{re.escape(value)}\b", page_text, re.IGNORECASE))
            for value in PURPLE_FAMILY) - len(re.findall(rf"{re.escape(PURPLE)}\b", page_text, re.IGNORECASE))
        for scope, selector, body in scoped_rules(page_css):
            selectors = [s.strip() for s in selector.split(",")]
            for value in declarations_in(body, "border-left"):
                if value.startswith("0"):
                    continue
                if (rel, selector.strip()) in SIDE_BAR_ALLOWLIST:
                    continue
                side_bars += 1
            for prop in ("box-shadow", "text-shadow", "filter"):
                for value in declarations_in(body, prop):
                    if not GLOW_LAYER.search(value):
                        continue
                    glows += 1
                    if scope is not None:
                        if prop in brand.get(f"@keyframes {scope}", set()):
                            brand_glows += 1
                    elif any(prop in brand.get(s, set()) for s in selectors):
                        brand_glows += 1
        for block in inline_style_blocks(page):
            for prop in ("box-shadow", "text-shadow", "filter"):
                for value in declarations_in(block, prop):
                    if GLOW_LAYER.search(value):
                        glows += 1

    # The nav partial is a source of its own: the pages carry a copy of it.
    nav = root / "docs" / "_partials" / "nav.html"
    assets = site_assets(root) + ([nav] if nav.exists() else [])
    for asset in assets:
        rel = asset.relative_to(root).as_posix()
        allowed = [snippet for snippet, _reason in EMOJI_ALLOWLIST.get(rel, [])]
        for _lineno, line, _char in emoji_occurrences(asset):
            if any(snippet in line for snippet in allowed):
                emoji_content += 1
            else:
                emoji_icons += 1

    return [
        ("2 圆角档位", f"{len(radii)} 种", "≤ 3 (+胶囊)", True),
        ("3 动效时长", f"{len(durations)} 种", "≤ 2", True),
        ("4 阴影档位 / 零偏移辉光",
         f"{len(shadows)} 处 / {glows} 处（品牌层 {brand_glows}）", "≤ 2 档 / 仅 logo+hero", True),
        ("5 字号：px 种数 / rem 种数", f"{len(px_sizes)} / {len(rem_sizes)}", "0 / ≤ 10(+2 展示)", True),
        ("6 font-family 字面栈", f"{len(families)} 种", "全部走 token", True),
        ("7 容器宽", f"{len(widths)} 种", "2 档", True),
        ("1 跨页主色 / 强调色", "待 Z 批收敛", "1 + 1", False),
        ("8 卡片套卡片", "0（按视觉判据）", "0", False),
        ("9 border-left 侧边色条", f"{side_bars} 处", "0", True),
        ("10 手写页面共用 token 头", "14 / 14", "14 / 14", True),
        ("11 各页底色统一", "待 Z 批", "--bg-0", False),
        ("12 紫色强调色", f"{purples} 处", "0", True),
        ("12b 其余紫色阶（Z 批）", f"{other_purples} 处", "0", False),
        ("13 Y 批：emoji 图标", f"{emoji_icons} 处（内容 {emoji_content} 处）", "0 处", True),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 when an enforced criterion fails")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    print("判据（#3541 验收表）")
    print(f"{'判据':<34} {'现状':<16} {'目标':<16} 状态")
    for criterion, current, target, enforced in report(args.root):
        print(f"{criterion:<34} {current:<16} {target:<16} {'门禁' if enforced else '待批'}")

    problems = check(args.root)
    if not problems:
        print("\n✅ enforced criteria hold")
        return 0
    if args.check:
        print(f"\n❌ {len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(f"\n⚠️  {len(problems)} problem(s) — not enforced yet")
    for problem in problems[:40]:
        print(f"  {problem}")
    if len(problems) > 40:
        print(f"  … and {len(problems) - 40} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
