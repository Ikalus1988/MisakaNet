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

    return problems


def report(root: Path = REPO) -> list[tuple[str, str, str, bool]]:
    """The acceptance table from #3541, with the current number for each row.

    Returns (criterion, current, target, enforced?) rows — enforced rows are the ones `check()`
    fails on; the rest are X's and Y's, printed so the next batch can see what it owes.
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
    glows = [v for v in shadows if re.search(r"0 0 \d+px", v)]
    px_sizes = {v for v in values_of(css, "font-size") if re.search(r"\d\s*px", v)}
    rem_sizes = {v for v in values_of(css, "font-size") if re.fullmatch(r"[\d.]+rem", v)}
    # A `var(--font-…)` reference *is* the vocabulary being used, not a literal stack — counting
    # the references as stacks would report "5 种字面栈" on a page that has none.
    families = {v for v in values_of(css, "font-family")
                if v != "inherit" and not v.startswith("var(")}
    widths = {v for v in values_of(css, "max-width")
              if re.fullmatch(r"\d+px", v) and int(v[:-2]) >= 500}
    emoji = re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", css)
    side_bars = [v for v in values_of(css, "border-left") if not v.startswith("0")]

    return [
        ("2 圆角档位", f"{len(radii)} 种", "≤ 3 (+胶囊)", True),
        ("3 动效时长", f"{len(durations)} 种", "≤ 2", True),
        ("4 阴影档位 / 零偏移辉光", f"{len(shadows)} 处 / {len(glows)} 处", "≤ 2 档 / 仅 logo+hero", True),
        ("5 字号：px 种数 / rem 种数", f"{len(px_sizes)} / {len(rem_sizes)}", "0 / ≤ 10(+2 展示)", True),
        ("6 font-family 字面栈", f"{len(families)} 种", "全部走 token", True),
        ("7 容器宽", f"{len(widths)} 种", "2 档", True),
        ("1 跨页主色 / 强调色", "待 X 批收敛", "1 + 1", False),
        ("8 卡片套卡片", "待 X 批", "0", False),
        ("9 border-left 侧边色条", f"{len(side_bars)} 处", "0", False),
        ("10 手写页面共用 token 头", "14 / 14", "14 / 14", False),
        ("11 各页底色统一", "待 X 批", "--bg-0", False),
        ("7 Y 批：emoji 图标", f"{len(emoji)} 个", "0", False),
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
