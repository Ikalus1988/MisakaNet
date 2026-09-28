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
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
INDEX = DOCS / "index.html"

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
    return DOCS / rel / "index.html" if not rel.endswith(".html") else DOCS / rel


# ── every internal link in every page, not only the drawer (2026-09-28) ───────────────────────────
#
# The drawer check above was written for #1892 and covers one menu on one page. The site is 480+ static
# files served verbatim out of `docs/`, so the same defect — a link to something that is not there — can
# be written anywhere, and nothing looked: the sweep that added this found two pages with three such
# links, one of them in a footer a visitor reaches from the insights pages.
#
# The rule is "a link resolves **or the worker serves that path**", and neither half is allowed to be a
# hand-written list:
#
#   * the file half is resolved like a browser resolves it (root-relative, or relative to the page),
#     including the two extensions Cloudflare's asset handling adds — `/x` → `x.html`, `/x/` →
#     `x/index.html` — because that is what makes `/start` work;
#   * the worker half is read out of `workers/register-proxy-sw.js`, the file that actually answers
#     those routes. A hard-coded exemption list would be a second place to forget, and its failure mode
#     is a gate that stays green while the route it exempts is deleted.

LINK = re.compile(r'href="([^"]+)"')
# Not links: another origin, an in-page anchor, or a non-http scheme.
_NON_LOCAL = ("http://", "https://", "//", "#", "mailto:", "tel:", "data:", "javascript:")
# JavaScript building a URL at runtime (`${...}`, `' + x + '`): not a link until the page runs, and a
# page that renders them is covered by the i18n/format tests, not by a static scan.
_TEMPLATED = ("${", "' +", '" +', "{{")
_WORKER = REPO / "workers" / "register-proxy-sw.js"


def worker_served_paths() -> frozenset[str]:
    """Exactly the paths `workers/register-proxy-sw.js` matches by name (plus the `/api/` prefix)."""
    source = _WORKER.read_text(encoding="utf-8")
    exact = set(re.findall(r'url\.pathname === "([^"]+)"', source))
    assert "/mcp" in exact and "/start" in exact, (
        f"the worker route scan found {sorted(exact)[:5]}… — the routes moved or the pattern changed, "
        "and every link below would then be judged against a stale exemption set"
    )
    return frozenset(exact)


WORKER_SERVED = worker_served_paths()


def is_worker_served(target: str) -> bool:
    return target in WORKER_SERVED or target.startswith("/api/")


def resolve_link(target: str, page: Path, docs: Path = DOCS) -> Path | None:
    """The file that serves `target` from `page`, or None when nothing does.

    `os.path.normpath` plus the clamp below are both load-bearing, and the control fixture exercises
    each: `docs/insights/x.html` linking `../reputation.md` is a *valid* link (a naive
    `Path("insights") / "../reputation.md"` keeps the `..` segment), and a browser **stops** at the
    site root, so `../../index.html` from `/sub/page.html` is `/index.html` rather than an escape.
    Deciding that by asking the filesystem would resolve paths outside the served root, which is how a
    link to `../../etc/passwd` would come back "fine" on a machine where that file exists.
    """
    if target.startswith("/"):
        rel = target.lstrip("/")
    else:
        rel = os.path.join(str(page.parent.relative_to(docs)), target)
    rel = os.path.normpath(rel)
    # Leading `..` cannot go above the origin: drop them (browser behaviour), then resolve what is left
    # inside `docs/`. Nothing outside `docs/` is servable, so it can never satisfy a link.
    rel = re.sub(r"^(?:\.\./)+", "", rel)
    candidate = docs / rel
    for path in (candidate, docs / rel / "index.html", Path(str(candidate) + ".html")):
        if path.is_file():
            return path
    return None


def broken_internal_links(docs: Path = DOCS) -> dict[str, list[str]]:
    """`{page: [link, …]}` for every internal link nothing serves. Empty dict == healthy."""
    broken: dict[str, list[str]] = {}
    for page in sorted(docs.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            raw = raw.strip()
            if not raw or raw.startswith(_NON_LOCAL) or any(t in raw for t in _TEMPLATED):
                continue
            target = raw.split("#")[0].split("?")[0]
            if not target or (target.startswith("/") and is_worker_served(target)):
                continue
            if resolve_link(target, page, docs) is None:
                broken.setdefault(page.relative_to(docs.parent).as_posix(), []).append(raw)
    return broken


def test_the_link_scanner_sees_the_site_and_can_fail(tmp_path):
    """Both halves of a gate: the corpus it claims to cover, and a control that makes it go red.

    A scanner that silently matched nothing (or resolved everything) is the failure this repository
    keeps finding in its own gates, so the negative control is here rather than assumed.
    """
    pages = list(DOCS.rglob("*.html"))
    assert len(pages) > 400, f"only {len(pages)} pages scanned — the glob moved"
    assert sum(len(LINK.findall(p.read_text(encoding='utf-8'))) for p in pages) > 1000, (
        "the href scan found implausibly few links — the pattern moved"
    )

    (tmp_path / "outside.html").write_text("outside the served root", encoding="utf-8")
    (tmp_path / "docs" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "index.html").write_text(
        '<a href="/there/">ok</a>'
        '<a href="gone.html">broken</a>'
        '<a href="/api/health">worker-served</a>'
        '<a href="/extensionless">ok, served from .html</a>'
        '<a href="../../outside.html">escapes the served root</a>',
        encoding="utf-8")
    # Two `..` segments from a page one level down still land on the site root (that is what a browser
    # does), so this must NOT be reported — the clamp rule is what the control is really for.
    (tmp_path / "docs" / "sub" / "page.html").write_text(
        '<a href="../../index.html">ok, clamped at the root</a>', encoding="utf-8")
    (tmp_path / "docs" / "there").mkdir()
    (tmp_path / "docs" / "there" / "index.html").write_text("ok", encoding="utf-8")
    # Only `extensionless.html` exists: Cloudflare's asset handling serves `/extensionless` from it, so
    # this case catches the day that rule is dropped from the resolver.
    (tmp_path / "docs" / "extensionless.html").write_text("ok", encoding="utf-8")
    found = broken_internal_links(tmp_path / "docs")
    # `outside.html` exists — one level above the served root — and is still reported: the filesystem
    # resolves that path happily, the site cannot serve it, and only the clamp tells the two apart.
    assert found == {"docs/index.html": ["gone.html", "../../outside.html"]}, found


def test_every_internal_link_in_docs_resolves():
    """The gate. `docs/**/*.html` is served verbatim, so a link to a missing file is a 404 on the site.

    Measured when this was added (2026-09-28): three broken links in two pages —
    `docs/insights/pr-genius.html` pointed at `/MisakaNet/` and `/MisakaNet/insights/…` (a
    GitHub-Pages-shaped path, which is a 404 on the domain the page is served from), and
    `docs/journey/index.html` linked `docs/label-system.md` from inside `docs/journey/` (one directory
    too deep). Both are fixed the same day; this test is what keeps the next one from shipping.
    """
    broken = broken_internal_links()
    detail = "\n  - ".join(f"{page}: {links}" for page, links in sorted(broken.items()))
    assert not broken, (
        "these internal links have nothing behind them (a file under `docs/`, or a route "
        f"`workers/register-proxy-sw.js` answers):\n  - {detail}"
    )


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
