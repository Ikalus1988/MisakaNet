#!/usr/bin/env python3
"""The drawer nav has one source, and the two copies cannot disagree silently.

Why this exists: the menu was edited in place four times in one week (adding `/install`, then the About
section), and the failure mode of a menu is *silent* — a page that no longer appears in it is still a live
URL, so nothing breaks and nobody is told. Four such pages sat that way for days (#1892).

The design is deliberately not a template engine: the site is served verbatim from `docs/` with no build
step, which is what lets the suite assert pages with regexes. So the shared markup is a partial plus a
checker, and this file is the checker's own test — including the tampered fixture that proves it can fail.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import sync_site_partials as ssp  # noqa: E402


def _copy_tree(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "_partials").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "docs" / "index.html", tmp_path / "docs" / "index.html")
    shutil.copy(REPO / "docs" / "_partials" / "nav.html", tmp_path / "docs" / "_partials" / "nav.html")
    return tmp_path


def test_the_page_and_the_partial_agree_today():
    assert ssp.check(REPO) == [], ssp.check(REPO)


def test_the_cli_passes_on_this_repository():
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_site_partials.py"), "--check"],
                          capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a_menu_edited_in_only_one_place_is_caught(tmp_path):
    """The control: without this, a checker that returns [] unconditionally would pass."""
    root = _copy_tree(tmp_path)
    partial = root / "docs" / "_partials" / "nav.html"
    partial.write_text(partial.read_text(encoding="utf-8").replace("</nav>", '<span>extra</span></nav>'),
                       encoding="utf-8")
    problems = ssp.check(root)
    assert problems and "nav.html" in problems[0], problems


def test_write_brings_the_page_back_to_the_partial(tmp_path):
    root = _copy_tree(tmp_path)
    partial = root / "docs" / "_partials" / "nav.html"
    partial.write_text(partial.read_text(encoding="utf-8").replace("</nav>", '<span>extra</span></nav>'),
                       encoding="utf-8")
    changed = ssp.write(root)
    assert changed == ["docs/index.html"], changed
    assert ssp.check(root) == [], "write did not reconcile the two copies"


def test_a_missing_nav_block_is_reported_rather_than_ignored(tmp_path):
    root = _copy_tree(tmp_path)
    page = root / "docs" / "index.html"
    page.write_text(page.read_text(encoding="utf-8").replace('<nav class="drawer"', '<nav class="gone"'),
                    encoding="utf-8")
    assert ssp.check(root), "a page with no nav block must be reported"
