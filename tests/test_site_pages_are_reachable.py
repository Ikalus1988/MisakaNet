#!/usr/bin/env python3
"""Every internal link on the homepage must have a page behind it, and every page must be reachable.

Why this file exists (2026-09-26): `/install`, `/enterprise/`, `/privacy/` and `/terms/` were all live
and none of them was linked from anywhere on the site — the only way to arrive was to type the URL. The
issue for the install page had been open since 2026-09-21 (#1892, "站点把自己的安装页藏起来了"), and the
other three were found while fixing it, which is the shape worth gating: **a page nobody links is a page
nobody has, and nothing in the suite noticed either direction.**

Two properties, both cheap to check and both previously unguarded:

1. **A drawer link resolves.** Each `href="/…"` in `docs/index.html` maps to a file on disk; a link to a
   page that does not exist is a 404 in the one menu a visitor actually uses. External links (`http…`),
   anchors (`#…`) and the few generated paths (`/mcp`) are out of scope, and `docs/_routes.json` carries
   the excludes Cloudflare serves itself.
2. **A page is reachable.** The four pages above are named here, so deleting their entries from the
   drawer fails this file rather than quietly returning them to the "type the URL" state. This is the
   half that would have caught #1892 when the page was written.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"

# Internal links only: `href="/x"` or `href="/x/"`. Absolute external URLs, in-page anchors and
# `mailto:`/`tel:` are other pages' business, and so is anything the worker serves instead of a file
# (`/mcp`, `/api/*` — the latter appears in curl examples, not in links).
INTERNAL = re.compile(r'href="(/[^"#?]*)"')

# Pages whose only entry point is the drawer, asserted by name so an accidental deletion is a failure
# rather than a silent regression to "reachable by typing the URL".
REACHABLE_FROM_THE_DRAWER = ("/install/", "/enterprise/", "/privacy/", "/terms/")


def drawer_targets() -> list[str]:
    text = INDEX.read_text(encoding="utf-8")
    drawer = text[text.index('<nav class="drawer"'):text.index("</nav>")]
    targets = []
    for raw in INTERNAL.findall(drawer):
        if raw in ("/", ""):
            continue
        targets.append(raw)
    assert targets, "no internal drawer links found — the drawer markup moved"
    return targets


def page_for(target: str) -> Path:
    """The file a `/x/` or `/x` link serves out of `docs/`."""
    rel = target.strip("/")
    return REPO / "docs" / rel / "index.html" if not rel.endswith(".html") else REPO / "docs" / rel


def test_every_drawer_link_has_a_page_behind_it():
    missing = [t for t in drawer_targets() if not page_for(t).exists()]
    assert not missing, (
        f"the drawer links pages that do not exist: {missing}. A 404 in the site's own menu is worse "
        "than no entry: it reads as a broken site rather than a missing page"
    )


def test_the_pages_that_used_to_be_unreachable_stay_linked():
    targets = set(drawer_targets())
    missing = [p for p in REACHABLE_FROM_THE_DRAWER if p not in targets]
    assert not missing, (
        f"these pages are no longer linked from the homepage: {missing}. /install was #1892 and the "
        "other three were live with no entry point at all; the drawer is their only path"
    )


def test_the_generated_pages_are_not_claimed_as_static_ones():
    """`/lessons/<slug>/` and `/topics/<slug>/` are generated (docs/.generated-pages.json).

    A drawer link into that tree would be a link to a page the generator owns and may prune — the exact
    coupling `build_lesson_pages.py` documents. Search and the topic index are the entry points for it.
    """
    manifest = json.loads((REPO / "docs" / ".generated-pages.json").read_text(encoding="utf-8"))
    generated = set(manifest["pages"])
    offenders = [t for t in drawer_targets()
                 if f"docs{t}index.html" in generated and t not in ("/search/",)]
    assert not offenders, f"the drawer links generated pages directly: {offenders}"


# ── the two things this page used to get wrong about itself (2026-09-27) ──────────────────────────
#
# Both were copy-level defects with a structural cause: the page described a *step* (register) as the way
# in, and described a *counter's* date as content freshness. Neither is a design question, which is why
# they are asserted here rather than left to review.

def test_the_page_does_not_claim_a_content_freshness_date():
    """`last updated <date>` read `counter.updated` — a registration counter, not the corpus.

    The daily job moves the corpus and the counter moves when someone registers; no date on the stats card
    can honestly claim the other. Removing it is the fix, not re-dating it: every timestamp on a page is a
    claim that has to be kept true, and the one date that *is* meaningful already lives in the activity
    panel where it belongs to the snapshot.
    """
    page = INDEX.read_text(encoding="utf-8")
    assert 'id="last-updated"' not in page, "the freshness label is back"
    # Comments are stripped first: the explanation of *why* the label is gone quotes it, and a test that
    # cannot tell prose from markup would forbid writing the reason down.
    rendered = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    assert "last updated" not in rendered, "a rewritten but equally misleading variant appeared"


def test_the_primary_entry_point_is_connecting_not_registering():
    """Reading needs no account (`AGENTS.md` §3.3), so the hero's first actionable line is `/install`."""
    page = INDEX.read_text(encoding="utf-8")
    assert 'href="/install/"' in page, "the primary CTA no longer points at the install page"
    hero_start = page.index('class="agent-register-bar"')  # the markup, not the CSS rule of the same name
    # The first `safety-notice` in the file is the CSS rule, so the search starts after the hero.
    hero = page[hero_start:page.index("safety-notice", hero_start)]
    assert 'href="/install/"' in hero, "the install link is no longer in the hero block"
    assert "agentInstallCta" in hero and "readNeedsNoRegistration" in hero, (
        "the hero no longer states what needs no account"
    )
    for lang in ("en", "zh"):
        dictionary = json.loads((REPO / "docs" / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        assert "agentInstallCta" in dictionary and "readNeedsNoRegistration" in dictionary, lang
        assert "register" in dictionary["agentRegisterHint"].lower() or "注册" in dictionary["agentRegisterHint"], (
            f"{lang}: the register hint no longer scopes itself to the write tools"
        )
