#!/usr/bin/env python3
"""Every README must carry the same badges as the canonical one.

What this is about is not "does the Chinese README look nice". Badges are the only part of a
README that is **not prose**, so they are the only part that has exactly one correct answer per
language: the same set of links, rendered with translated `alt` text. A sentence can be
reworded in translation; a CI badge either points at this repository's workflow or it does not.

The concrete failure this pins is `README.zh-CN.md` carrying **4 of `README.md`'s 19** badges
(measured 2026-10-11) — no CI, no MCP tool count, no retrieval backend, no Python/PyPI/npm, and
none of the nine ecosystem badges. `README.ja.md` carried 19 of 19, so the drift was not a policy
of "translations get a smaller set"; it was drift with no writer to notice. The cost was not
cosmetic: `README.zh-CN.md:102` told readers

    当前发布到 npm 的版本见**本页上方的 npm 徽章**

and there was no npm badge anywhere on the page — the sentence pointed a reader at a region of
the document and told them to find something that was not there.

Why no gate existed
-------------------
`sync_lesson_count.py` owns the *count inside* the lessons badge, and
`tests/test_lesson_count_ssot.py` owns which surfaces may quote a count. Neither asks whether a
translation still carries the badge at all, and `tests/test_readme_asset_budget.py` only walks
markdown `![...](...)` images — shields.io badges are HTML `<img>` inside `<a>`, so they are
invisible to it. Every badge gate that exists was therefore green on a README missing 15 of 19.

How this stays honest
---------------------
The truth is read from `README.md` at runtime, never hardcoded — a gate that hardcodes "19" is
wrong the day someone adds a twentieth badge, and wrong silently. `alt` text is deliberately
**not** compared: `README.zh-CN.md` renders the lessons badge as `知识` and the English one as
`Lessons`, which is correct translation, not drift. The `href` is what has to match, because
that is what a reader's click lands on.

Usage:
    python3 tests/test_readme_badge_parity.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# README.md is the canonical one; the others are translations of it.
CANONICAL = "README.md"
TRANSLATIONS = ("README.ja.md", "README.zh-CN.md")

# A badge is a link wrapping an image. Anchoring on `<a href=` followed by `<img src=` is what
# separates a badge from every other image on the page: the promotional hero art is a bare
# `<img>`, and an inline prose link has no image inside it.
BADGE = re.compile(r'<a href="([^"]+)"><img src="[^"]+"[^>]*alt="[^"]*"', re.S)


def badges(name: str) -> list[str]:
    """The badge hrefs in one README, in document order."""
    return BADGE.findall((REPO / name).read_text(encoding="utf-8"))


def _duplicates(hrefs: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for href in hrefs:
        if href in seen:
            dupes.add(href)
        seen.add(href)
    return sorted(dupes)


def test_canonical_readme_has_badges_to_compare_against() -> None:
    """A parity gate over an empty canonical set passes vacuously and reads as coverage.

    `tests/test_first_run_path_is_true.py` makes the same argument about a list that no longer
    exists in the code it claims to check. If a refactor moved the badges out of README.md into
    an include, this gate would compare three empty sets forever.
    """
    canonical = badges(CANONICAL)
    assert canonical, (
        f"no badges parsed out of {CANONICAL}. The extractor is `re` over "
        f'`<a href="..."><img src="..." alt="..."`. If the badge block moved, fix this gate '
        f"rather than deleting the comparison — a parity check over nothing is not a check."
    )


def test_translations_carry_every_canonical_badge() -> None:
    """Each translation links the same badges the canonical README does."""
    canonical = badges(CANONICAL)
    expected = set(canonical)
    problems: list[str] = []

    for name in TRANSLATIONS:
        found = badges(name)
        if not found:
            problems.append(f"{name}: no badges found at all — see test_canonical_readme_has_badges")
            continue
        missing = expected - set(found)
        extra = set(found) - expected
        if missing:
            problems.append(
                f"{name}: missing {len(missing)} badge(s) present in {CANONICAL}:"
                + "".join(f"\n    - {href}" for href in sorted(missing))
            )
        if extra:
            problems.append(
                f"{name}: has {len(extra)} badge(s) {CANONICAL} does not:"
                + "".join(f"\n    - {href}" for href in sorted(extra))
            )
        dupes = _duplicates(found)
        if dupes:
            problems.append(f"{name}: the same badge is linked twice:" + "".join(
                f"\n    - {href}" for href in dupes))

    assert not problems, (
        "the translated READMEs have drifted from the canonical one:\n  - "
        + "\n  - ".join(problems)
        + f"\n\n{CANONICAL} links {len(canonical)} badges. A translation may render the same "
        f"badge with translated `alt` text — that is translation, not drift. What has to match "
        f"is the `href`, because that is where the reader's click lands."
    )


def test_badge_order_matches_so_the_header_reads_the_same_way() -> None:
    """Same set, different order, still a drifted page.

    `Core` reads before `Install` reads before `Ecosystem` in `README.md`; a translation that
    lists the ecosystem badge first shows the reader a different page.
    """
    canonical = badges(CANONICAL)
    for name in TRANSLATIONS:
        found = badges(name)
        if not found:
            continue  # reported by the set comparison, with better detail
        assert found == canonical, (
            f"{name} lists the same badges as {CANONICAL} in a different order.\n"
            f"  {CANONICAL}: {canonical}\n"
            f"  {name}: {found}"
        )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}\n  {exc}\n")
        else:
            print(f"ok   {name}")
    print(f"\n{'FAILED' if failures else 'passed'}: {failures} failure(s)")
    sys.exit(1 if failures else 0)