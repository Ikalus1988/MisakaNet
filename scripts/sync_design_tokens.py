#!/usr/bin/env python3
"""One source for the site's design tokens, checked rather than remembered (2026-10-20).

Issue #3541 wants one visual language across the site's hand-written pages. It is currently two
products: the homepage has an identity of its own, and the other hand-written pages are GitHub's
default dark theme, copied in from somewhere else. Fourteen pages, fourteen sets of hardcoded
colours, radii, shadows, font stacks and container widths — and every future change has to be
made fourteen times, or not at all.

The fix is a token vocabulary. This script is the *first* step of it (batch "V"): the tokens
exist, in one place, and every hand-written page carries the same copy of them.

    python3 scripts/sync_design_tokens.py --check    # exit 1 when a page drifted from the source
    python3 scripts/sync_design_tokens.py            # rewrite the pages from the source

The design is deliberately not a template engine and deliberately not a stylesheet link. The site
is served verbatim from `docs/` with no build step, which is what lets the suite assert pages
with regexes — and a `<link>` would put the tokens in a *second* request that the page's own
inline rules could not see, so "one source" would be true only until the first override. So the
tokens are copied into each page, and the copies are gated.

Two properties of the copy are load-bearing:

  * The block is inserted **before** the page's own `<style>`, so a page that defines a name the
    tokens also define still wins. Today that is `--font-ui` (homepage and search page) and
    `--font-mono` (search page): the pages' own stacks are left exactly as they were, so nothing
    changes visually in this batch. Making the tokens authoritative is batch "W"'s job, and doing
    both at once would make a visual regression impossible to attribute.
  * The block is delimited by `<!-- design-tokens:start -->` / `<!-- design-tokens:end -->`, so a
    page's copy can be compared to the source *as a whole*. A page that edited one value inside
    the block is drift, exactly like a page that deleted the block.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOKENS = Path("docs") / "_partials" / "design-tokens.html"
TOKEN_BLOCK = re.compile(r"<!-- design-tokens:start -->[\s\S]*?<!-- design-tokens:end -->")
# The anchor every hand-written page has, and the only one this script needs: each of them
# carries at least one inline `<style>`. `docs/search/danmaku-widget.html` has no `<head>` at all
# — it is a floating widget fragment — so anchoring on `<head>` would exclude it, and a token
# vocabulary that silently misses a page is worse than one that covers every page.
STYLE_OPEN = re.compile(r"<style\b[^>]*>")


def token_block(root: Path = REPO) -> str:
    """The marked block, markers included, as every page must carry it."""
    text = (root / TOKENS).read_text(encoding="utf-8")
    match = TOKEN_BLOCK.search(text)
    if not match:
        raise SystemExit(f"{TOKENS.as_posix()}: the design-tokens markers are gone")
    return match.group(0)


def token_pages(root: Path = REPO) -> list[Path]:
    """Every hand-written page, discovered — so a new page is covered by default.

    Discovery, not a list: a list of sixteen paths is a list that goes stale, and the failure is
    silent (the new page just misses the vocabulary). The generated pages — the mkdocs lesson and
    topic trees — are excluded by path, the same way `sync_site_partials.py` excludes them.
    """
    pages = sorted((root / "docs").rglob("*.html"))
    out = []
    for page in pages:
        rel = page.relative_to(root / "docs")
        if "_partials" in rel.parts or "lessons" in rel.parts or "topics" in rel.parts:
            continue
        out.append(page)
    return out


def check(root: Path = REPO) -> list[str]:
    """Every place a page and the token source disagree."""
    want = token_block(root).strip()
    problems: list[str] = []
    for page in token_pages(root):
        rel = page.relative_to(root).as_posix()
        text = page.read_text(encoding="utf-8")
        have = TOKEN_BLOCK.search(text)
        if have is None:
            problems.append(f"{rel}: no design-tokens block — run `python3 scripts/sync_design_tokens.py`")
        elif have.group(0).strip() != want:
            problems.append(
                f"{rel}: the design-tokens block differs from {TOKENS.as_posix()} — run "
                "`python3 scripts/sync_design_tokens.py` (a token edited in one place only is how "
                "two pages end up with two designs, #3541)")
    return problems


def write(root: Path = REPO) -> list[str]:
    """Rewrite the pages from the source. Returns the files changed, as POSIX relative paths.

    ``as_posix()``, not ``str()``: callers compare these against literals like ``"docs/index.html"``,
    and on Windows ``str(Path("docs") / "index.html")`` is ``docs\\index.html``. That is what made
    `tests/test_site_nav_single_source.py` fail on every ``windows-latest`` leg from the day the
    sibling script landed (#2365) — and a cross-platform job that is red for a reason unrelated to
    the change under review is a job nobody reads.
    """
    want = token_block(root).strip()
    changed: list[str] = []
    for page in token_pages(root):
        rel = page.relative_to(root).as_posix()
        text = page.read_text(encoding="utf-8")
        if TOKEN_BLOCK.search(text):
            new_text = TOKEN_BLOCK.sub(lambda _: want, text, count=1)
        else:
            style = STYLE_OPEN.search(text)
            if style is None:
                continue
            at = style.start()
            new_text = text[:at] + want + "\n" + text[at:]
        if new_text != text:
            page.write_text(new_text, encoding="utf-8")
            changed.append(rel)
    return changed


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
        print(f"✅ {TOKENS.as_posix()} and its pages agree")
        return 0
    changed = write(args.root)
    print(f"✅ rewrote {changed}" if changed else "✅ already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
