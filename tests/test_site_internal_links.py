#!/usr/bin/env python3
"""Every site-relative link in the deployed docs must target a page that exists (issue #1892).

Why this exists (2026-09-23): `/install/` has shipped since #1805, but no HTML page on the
site linked it — a visitor landing on the homepage could not reach the install page, and the
"install" entries in the drawer pointed at GitHub blob pages instead. Nothing noticed because
no test resolves links; `tests/test_setup_docs_consistency.py` watches commands, not
reachability. This is the missing target-side guard.

Resolution mirrors how Cloudflare Pages serves the deployed site: `/install/` →
`docs/install/index.html`, `/start` → `docs/start.html` (clean URLs, verified live 2026-09-23).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
PAGES = sorted(DOCS.glob("*.html")) + sorted(DOCS.glob("*/index.html"))
HREF = re.compile(r'href="(/[^"]*)"')


def resolves(href: str) -> bool:
    """A site-relative href is servable if it maps to a file, a directory index, or a clean URL.

    Query strings and fragments are stripped first; `//` (protocol-relative) and `#`-only
    links never reach the site's own file tree.
    """
    path = href.split("#", 1)[0].split("?", 1)[0].lstrip("/")
    if not path:
        return True
    target = DOCS / path
    return (
        target.is_file()
        or (target / "index.html").is_file()
        or target.with_suffix(".html").is_file()
    )


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(REPO)))
def test_every_site_relative_href_targets_an_existing_page(page: Path) -> None:
    body = page.read_text(encoding="utf-8")
    broken = sorted({href for href in HREF.findall(body) if not resolves(href)})
    assert not broken, f"{page.relative_to(REPO)} links site pages that do not exist: {broken}"


def test_the_homepage_links_the_install_page() -> None:
    """The exact failure of #1892: the page existed, the path to it did not."""
    body = (DOCS / "index.html").read_text(encoding="utf-8")
    assert 'href="/install/"' in body, (
        "the homepage must link /install/ — before #1892 the install page existed "
        "but no page on the site reached it"
    )


def test_the_homepage_drawer_links_the_quickstart_anchor() -> None:
    """The drawer's Quickstart entry needs its anchor to exist on the same page."""
    body = (DOCS / "index.html").read_text(encoding="utf-8")
    assert 'href="#quickstart"' in body and 'id="quickstart"' in body
