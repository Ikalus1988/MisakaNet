#!/usr/bin/env python3
"""One source for the site's shared markup, checked rather than remembered (2026-09-27).

The homepage carries a drawer navigation that lists every entry point a visitor can reach. It was edited
in place several times this week (adding `/install`, then the About section with enterprise/privacy/terms),
and each edit was a chance to leave the menu inconsistent with the pages it points at — which is exactly
what let four pages sit unlinked for days (#1892).

A template engine would solve this properly and cost the property that makes this site cheap to verify: it
is plain HTML served verbatim from `docs/`, so every page can be asserted with a regex in the test suite
(`tests/test_site_pages_are_reachable.py`, `test_site_i18n.py`, …). So the shared markup lives in
`docs/_partials/*.html` as the single source, and this script is the sync **and** the gate:

    python3 scripts/sync_site_partials.py --check    # exit 1 when a page drifted from the partial
    python3 scripts/sync_site_partials.py            # rewrite the pages from the partials

The pages stay static and the suite keeps its grip; what is removed is the ability for the two copies to
disagree without anyone noticing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INDEX = Path("docs") / "index.html"
PARTIALS = {"nav": Path("docs") / "_partials" / "nav.html"}
# The block the partial owns inside the page, matched by its element rather than by line numbers.
NAV_BLOCK = re.compile(r'<nav class="drawer"[\s\S]*?</nav>')


def extract_nav(text: str) -> str | None:
    match = NAV_BLOCK.search(text)
    return match.group(0) if match else None


def partial_body(path: Path) -> str:
    """The partial's markup, without its explanatory comment."""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"<!--[\s\S]*?-->\s*", "", text, count=1).strip()


def check(root: Path = REPO) -> list[str]:
    """Every place a page and its partial disagree."""
    problems: list[str] = []
    page = (root / INDEX).read_text(encoding="utf-8")
    current = extract_nav(page)
    if current is None:
        return [f"{INDEX.as_posix()}: the drawer nav block is gone (or its element changed)"]
    want = partial_body(root / PARTIALS["nav"])
    if current.strip() != want.strip():
        problems.append(
            f"{INDEX.as_posix()}: the drawer nav differs from {PARTIALS['nav'].as_posix()} — run "
            "`python3 scripts/sync_site_partials.py` (a menu edited in one place only is how pages end up "
            "unlinked, #1892)")
    return problems


def write(root: Path = REPO) -> list[str]:
    """Rewrite the page from the partial. Returns the files changed, as POSIX relative paths.

    ``as_posix()``, not ``str()``: callers compare these against literals like ``"docs/index.html"``,
    and on Windows ``str(Path("docs") / "index.html")`` is ``docs\\index.html``. That is what made
    ``tests/test_site_nav_single_source.py::test_write_brings_the_page_back_to_the_partial`` fail on
    every ``windows-latest`` leg from the day this script landed (2026-09-28, #2365) — and a
    cross-platform job that is red for a reason unrelated to the change under review is a job nobody
    reads, which is how the *next* Windows-only defect ships unnoticed. The path shape is part of this
    function's contract now, not an accident of where it ran.
    """
    path = root / INDEX
    page = path.read_text(encoding="utf-8")
    want = partial_body(root / PARTIALS["nav"])
    if extract_nav(page) is None:
        raise SystemExit(f"{INDEX.as_posix()}: no nav block to replace")
    updated = NAV_BLOCK.sub(lambda _: want, page, count=1)
    if updated == page:
        return []
    path.write_text(updated, encoding="utf-8")
    return [INDEX.as_posix()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify only; exit 1 on drift")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.check:
        problems = check(args.root)
        if problems:
            for problem in problems:
                print(f"❌ {problem}", file=sys.stderr)
            return 1
        print(f"✅ {PARTIALS['nav'].as_posix()} and {INDEX.as_posix()} agree")
        return 0
    changed = write(args.root)
    print(f"✅ rewrote {changed}" if changed else "✅ already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
