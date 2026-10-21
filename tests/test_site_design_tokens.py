#!/usr/bin/env python3
"""The design tokens have one source, and the fourteen copies cannot disagree silently.

Why this exists: the site holds two products (#3541) — a homepage with an identity of its own and
thirteen hand-written pages in GitHub's default dark theme, each with its own hardcoded colours,
radii, shadows and font stacks. The failure mode of a token vocabulary is *silent*: a page that
drifts from the vocabulary still renders, still looks plausible, and still disagrees with the
other thirteen. Nothing breaks and nobody is told.

This file is the checker's own test — including the tampered fixtures that prove it can fail. A
checker that returned [] unconditionally would pass everything else in this file, and a vocabulary
gate that cannot fail is a gate that has stopped gating.

The batch this lands is "zero risk" on purpose: the tokens are copied into every page but nothing
references them yet, and the copy sits *before* each page's own rules so a page that already
defines one of these names still wins. That is what keeps this batch visually inert, and the
last test below is what holds it there.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import sync_design_tokens as sdt  # noqa: E402

# The hand-written pages, by hand. The script discovers them, and the discovery is tested
# separately — but the *expectation* "these fourteen pages carry the vocabulary" is the issue's
# own acceptance criterion (#3541, criterion 10), so it is asserted here by name.
HAND_WRITTEN_PAGES = [
    "docs/index.html",
    "docs/start.html",
    "docs/connect.html",
    "docs/search/index.html",
    "docs/search/danmaku-widget.html",
    "docs/install/index.html",
    "docs/enterprise/index.html",
    "docs/privacy/index.html",
    "docs/terms/index.html",
    "docs/journey/index.html",
    "docs/journey/http-mcp/index.html",
    "docs/insights/lesson-coverage.html",
    "docs/insights/pr-genius.html",
    "docs/insights/reputation-leaderboard.html",
    "docs/insights/unsolved-map.html",
]


def _copy_tree(tmp_path: Path) -> Path:
    """A minimal tree: the token source and two pages, one of them with a block already."""
    (tmp_path / "docs" / "_partials").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "docs" / "_partials" / "design-tokens.html",
                tmp_path / "docs" / "_partials" / "design-tokens.html")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "docs" / "index.html", tmp_path / "docs" / "index.html")
    shutil.copy(REPO / "docs" / "start.html", tmp_path / "docs" / "start.html")
    return tmp_path


def test_the_pages_and_the_token_source_agree_today():
    assert sdt.check(REPO) == [], sdt.check(REPO)


def test_the_cli_passes_on_this_repository():
    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_design_tokens.py"), "--check"],
                          capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a_token_edited_in_one_place_is_caught(tmp_path):
    """The control: without this, a checker that returns [] unconditionally would pass."""
    root = _copy_tree(tmp_path)
    source = root / "docs" / "_partials" / "design-tokens.html"
    source.write_text(source.read_text(encoding="utf-8").replace("--accent:   #00e5ff", "--accent:   #00ff00"),
                      encoding="utf-8")
    problems = sdt.check(root)
    assert problems and "design-tokens" in problems[0], problems


def test_a_page_missing_the_block_is_reported_rather_than_ignored(tmp_path):
    root = _copy_tree(tmp_path)
    page = root / "docs" / "start.html"
    page.write_text(sdt.TOKEN_BLOCK.sub("", page.read_text(encoding="utf-8")), encoding="utf-8")
    problems = sdt.check(root)
    assert problems and "start.html" in problems[0], problems


def test_write_brings_the_page_back_to_the_source(tmp_path):
    root = _copy_tree(tmp_path)
    page = root / "docs" / "start.html"
    page.write_text(sdt.TOKEN_BLOCK.sub("", page.read_text(encoding="utf-8")), encoding="utf-8")
    changed = sdt.write(root)
    assert "docs/start.html" in changed, changed
    # The *shape* of that path is part of the contract: `str(Path("docs") / "start.html")` is
    # `docs\start.html` on Windows, which made the sibling gate red on every `windows-latest` leg
    # from the day it landed (#2365).
    assert all("\\" not in path for path in changed), changed
    assert sdt.check(root) == [], "write did not reconcile the copy"


def test_the_generated_pages_carry_the_block_too():
    """The generated pages are part of the site's design system (2026-10-21).

    They used to be excluded — and the exclusion was written out three times, once per script —
    so 571 pages carried their own hardcoded palette with nothing watching them (handoff §122.6
    item 2: "生成的 571 个课程页**不在门禁范围内**"). The generator copies this very source into
    them, so the copy is the same copy the hand-written pages carry.
    """
    generated = sorted((REPO / "docs" / "lessons").rglob("*.html"))
    assert generated, "the lesson tree is expected to exist"
    want = sdt.token_block(REPO).strip()
    for page in generated[:20]:
        text = page.read_text(encoding="utf-8", errors="replace")
        have = sdt.TOKEN_BLOCK.search(text)
        assert have is not None, f"{page}: the generated page carries no design-tokens block"
        assert have.group(0).strip() == want, f"{page}: the generated page carries a different block"


def test_a_drifted_generated_page_is_reported_with_the_generator_as_the_fix(tmp_path):
    """The control: the checker must see the generated tree, and must name the writer that
    actually owns those pages.

    Their writer is `scripts/build_lesson_pages.py` — a second writer for the same file is how a
    page ends up with two sources of truth (handoff §122.3) — so naming the wrong script would
    send the reader to one that will not touch the file.
    """
    root = _copy_tree(tmp_path)
    page = root / "docs" / "lessons" / "probe" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("<html><body>no tokens here</body></html>", encoding="utf-8")
    problems = sdt.check(root)
    assert any("build_lesson_pages.py" in p for p in problems), problems


def test_the_sync_script_does_not_rewrite_the_generated_pages(tmp_path):
    """One writer per file: the generator owns the generated pages, this script owns the rest."""
    root = _copy_tree(tmp_path)
    page = root / "docs" / "lessons" / "probe" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("<html><body>no tokens here</body></html>", encoding="utf-8")
    sdt.write(root)
    assert "design-tokens" not in page.read_text(encoding="utf-8"), (
        "the sync script rewrote a generated page — the generator is its only writer")


def test_every_hand_written_page_carries_the_same_block():
    """Issue #3541, criterion 10: the hand-written pages share one token header."""
    want = sdt.token_block(REPO).strip()
    for rel in HAND_WRITTEN_PAGES:
        page = REPO / rel
        if not page.exists():
            # `docs/connect.html` is named in the issue but is not in the tree; a page that does
            # not exist cannot carry tokens, and the gate must not pretend it does.
            continue
        text = page.read_text(encoding="utf-8")
        have = sdt.TOKEN_BLOCK.search(text)
        assert have is not None, f"{rel} carries no design-tokens block"
        assert have.group(0).strip() == want, f"{rel} carries a different block"


def test_the_tokens_are_inert_today():
    """The batch's promise: a vocabulary, not a redesign.

    The block is inserted *before* each page's own rules, so a page that already defines one of
    these names still wins. Without that order the batch would silently change the homepage and
    the search page — the two pages that define `--font-ui` and `--font-mono` — and a visual
    regression would arrive dressed as a token cleanup.
    """
    for page in sdt.token_pages(REPO):
        text = page.read_text(encoding="utf-8")
        block_at = text.find("<!-- design-tokens:start -->")
        style_at = text.find("<style")
        assert block_at != -1, page
        assert style_at != -1, f"{page} has no style block to sit in front of"
        assert block_at < style_at, (
            f"{page}: the tokens are injected after the page's own rules, so they would override "
            "the page instead of the other way round")
