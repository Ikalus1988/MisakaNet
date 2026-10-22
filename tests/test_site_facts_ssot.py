#!/usr/bin/env python3
"""Site-facts SSOT invariants (#1895).

Background — the failure these tests exist to prevent
----------------------------------------------------
The homepage Quickstart and the README each hand-wrote the same commands:

    docs/index.html  "npx @misaka-net/misakanet-setup"   (Track A step 1)
    README.md        "npx @misaka-net/misakanet-setup"   ("How to use it" installer row)

Nothing compared them, so a one-character drift (a renamed npm package, a dropped flag) was
invisible to CI: the site would teach a command the README does not. The tool count was not
merely ungoverned but wrong — the homepage's self-check sentence said "misakanet with 7 tools"
while ``canonical_mcp_tools()`` has been 8 since ``misakanet_me_inbox`` landed. Every other
surface that retypes the hosted count is pinned by ``tests/test_mcp_tool_count_ssot.py``; the
homepage sentence was never on that list.

``scripts/sync_site_facts.py`` is the writer: README.md is the source of the command strings
and the homepage is a copy it makes; the tool count is rewritten through the same ``Site``
machinery ``scripts/sync_lesson_count.py`` uses, over three rows — the homepage's static
sentence **and** the two ``qsAVerify`` dictionary values that overwrite it at render time.

That third leg was found the hard way. The first version of this gate fixed the HTML fallback
from 7 to 8 and stopped there, while ``docs/locales/*.json`` kept saying 7 — and because ``t()``
prefers the dictionary, the live page still showed 7. A second handwritten source of a managed
fact, invisible to ``grep docs/index.html``. These tests pin four properties:

1. the gate is green on the tree as committed, on every tool-count row (homepage + both locales);
2. it can go red, and a red run names **both** files with their lines — the reader needs to see
   the two spellings side by side, not only which one "won";
3. the capture patterns are anchored on the surrounding prose rather than on the command text,
   which is the only reason a corrupted command is *captured and compared* instead of silently
   reported as "pattern not found";
4. a stale dictionary value fails the check naming its file — the exact gap that shipped.
"""
from __future__ import annotations

import shutil
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import sync_site_facts as ssf  # noqa: E402
from scripts.sync_lesson_count import Site, sync_all  # noqa: E402

WORKFLOWS = (
    REPO / ".github" / "workflows" / "pr-checks.yml",
    REPO / ".github" / "workflows" / "docs.yml",
)


# ── the gate, green on the committed tree ────────────────────────────────────────────────────────

def test_every_managed_command_matches_across_surfaces():
    problems = ssf.stale_command_entries()
    assert problems == [], (
        "homepage Quickstart commands drifted from README.md:\n  - "
        + "\n  - ".join(problems)
        + "\nFix: python3 scripts/sync_site_facts.py"
    )


def test_the_homepage_tool_count_matches_the_canonical_one():
    """The sentence said 7 while the served set has been 8; it is now written, not retyped."""
    problems = ssf.stale_tool_count_entries()
    assert problems == [], (
        "homepage tool count drifted:\n  - " + "\n  - ".join(problems)
        + "\nFix: python3 scripts/sync_site_facts.py"
    )


def test_the_locale_tool_counts_are_on_the_same_writer():
    """The dictionary values render *over* the HTML fallback, so they are the live sentence.

    The first version of this gate fixed only the HTML and the page kept showing 7 — the exact
    "second handwritten source" 验收 #2 forbids. All three rows must sit in TOOL_SITES.
    """
    paths = [site.path for site in ssf.TOOL_SITES]
    for required in ("docs/index.html", "docs/locales/en.json", "docs/locales/zh.json"):
        assert paths.count(required) == 1, (required, paths)
    from scripts.sync_lesson_count import canonical_mcp_tools
    canonical = canonical_mcp_tools(REPO)
    for lang, phrase in (("en", rf"misakanet with {canonical} tools"),
                         ("zh", rf"misakanet 与 {canonical} 个工具")):
        text = (REPO / "docs" / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        assert phrase in text, (
            f"docs/locales/{lang}.json does not state the canonical tool count ({canonical}) — "
            f"the rendered page will show whatever the dictionary says"
        )


def test_a_stale_locale_tool_count_names_its_file(tmp_path):
    """The gap that shipped: the dictionary said 7 while the HTML (and the worker) said 8."""
    (tmp_path / "docs" / "locales").mkdir(parents=True)
    (tmp_path / "docs" / "locales" / "en.json").write_text(
        '"qsAVerify": "…misakanet with 7 tools…"', encoding="utf-8")
    from scripts.sync_lesson_count import stale_entries
    problems = stale_entries(8, root=tmp_path, sites=ssf.TOOL_SITES, check_count_file=False)
    named = [p for p in problems if "docs/locales/en.json" in p]
    assert named, problems
    assert "should be 8" in named[0], named[0]


# ── and it can go red, naming both files ─────────────────────────────────────────────────────────

def _mini_tree(tmp_path: Path) -> Path:
    """A root with just the surfaces a command fact reads.

    Copying the real files keeps the patterns honest — a fixture that this file also wrote would
    pass even if the patterns matched nothing in the repository. The install page is one of those
    surfaces since #3640: the page that teaches the command must not spell it differently from
    the README it points at.
    """
    (tmp_path / "docs" / "install").mkdir(parents=True)
    shutil.copy(REPO / "README.md", tmp_path / "README.md")
    shutil.copy(REPO / "docs" / "index.html", tmp_path / "docs" / "index.html")
    shutil.copy(
        REPO / "docs" / "install" / "index.html", tmp_path / "docs" / "install" / "index.html"
    )
    return tmp_path


def test_a_one_character_corruption_on_the_homepage_names_both_files(tmp_path):
    """验收 #1: change one character of the install command → the check fails citing both files.

    The error must carry both paths and both spellings — a message that says only "drift" sends
    the reader hunting, which is half of why this went unnoticed for so long.
    """
    root = _mini_tree(tmp_path)
    index = root / "docs" / "index.html"
    text = index.read_text(encoding="utf-8")
    # The wrapper is not the subject: #3491 wrapped the command in a row and an id for its copy
    # button, and a test that pins the wrapper would have to be edited by every UI change. What it
    # pins is the command text inside whichever `.qs-cmd` holds it.
    pattern = re.compile(r'(<div class="qs-cmd"[^>]*>)npx @misaka-net/misakanet-setup(</div>)')
    assert len(pattern.findall(text)) == 1, "the homepage install command moved — update this test with it"
    index.write_text(pattern.sub(r"\1npx @misaka-net/misakanet-setuq\2", text, count=1), encoding="utf-8")

    problems = ssf.stale_command_entries(root=root)
    assert problems, "a one-character corruption of the homepage command passed the check"
    joined = "\n".join(problems)
    assert "README.md" in joined, joined
    assert "docs/index.html" in joined, joined
    assert "npx @misaka-net/misakanet-setup" in joined, joined
    assert "npx @misaka-net/misakanet-setuq" in joined, joined


def test_sync_rewrites_the_mirror_from_the_source(tmp_path):
    """One writer: the README is the origin, the homepage is a copy the script makes."""
    root = _mini_tree(tmp_path)
    index = root / "docs" / "index.html"
    text = index.read_text(encoding="utf-8")
    pattern = re.compile(r'(<div class="qs-cmd"[^>]*>)npx @misaka-net/misakanet-setup(</div>)')
    index.write_text(
        pattern.sub(r"\1npx @misaka-net/misakanet-setuq\2", text, count=1), encoding="utf-8")

    changes, errors = ssf.sync_command_facts(root=root)
    assert errors == [], errors
    assert changes, "the corrupted mirror was not rewritten"
    assert ssf.stale_command_entries(root=root) == []
    assert "npx @misaka-net/misakanet-setup</div>" in index.read_text(encoding="utf-8")
    assert "setuq" not in index.read_text(encoding="utf-8")


def test_the_tool_count_site_rewrites_again_on_a_second_run(tmp_path):
    """The lesson-count write-once bug, pinned for this row family: a second run must rewrite again.

    Driven through ``sync_all`` (the machinery ``sync_tool_count`` delegates to) with an explicit
    count, because ``canonical_mcp_tools`` measures the real AGENTS.md/worker pair and has no
    meaning inside a fixture tree. All three rows are exercised together — the HTML fallback and
    the two dictionary values must move as one, which is the whole point of putting them under
    one writer.
    """
    (tmp_path / "docs" / "locales").mkdir(parents=True)
    targets = {
        "docs/index.html": ("shows misakanet with 7 tools", "shows misakanet with {} tools"),
        "docs/locales/en.json": ('"qsAVerify": "…misakanet with 7 tools…"',
                                 '"qsAVerify": "…misakanet with {} tools…"'),
        "docs/locales/zh.json": ('"qsAVerify": "…misakanet 与 7 个工具…"',
                                 '"qsAVerify": "…misakanet 与 {} 个工具…"'),
    }
    for rel, (text, _) in targets.items():
        (tmp_path / rel).write_text(text, encoding="utf-8")

    changes, errors = sync_all(8, root=tmp_path, sites=ssf.TOOL_SITES, write_count_file=False)
    assert errors == [], errors
    assert len(changes) == len(ssf.TOOL_SITES), changes
    for rel, (_, template) in targets.items():
        assert (tmp_path / rel).read_text(encoding="utf-8") == template.format(8)

    changes, errors = sync_all(9, root=tmp_path, sites=ssf.TOOL_SITES, write_count_file=False)
    assert errors == [], errors
    assert len(changes) == len(ssf.TOOL_SITES), (
        "a second sync with a different count found nothing to rewrite (write-once)", changes)
    for rel, (_, template) in targets.items():
        assert (tmp_path / rel).read_text(encoding="utf-8") == template.format(9)


def test_a_reworded_tool_count_sentence_is_an_error_not_a_skip(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.html").write_text(
        "shows misakanet with seven tools", encoding="utf-8")
    from scripts.sync_lesson_count import stale_entries
    problems = stale_entries(8, root=tmp_path, sites=ssf.TOOL_SITES, check_count_file=False)
    assert problems, "a reworded sentence must fail loudly, never silently skip"
    assert "docs/index.html" in problems[0]


# ── the patterns must capture corruption, not miss it ────────────────────────────────────────────

def _flip_one_alnum(text: str) -> str:
    for i in range(len(text) - 1, -1, -1):
        if text[i].isalnum():
            return text[:i] + ("X" if text[i].islower() else "x") + text[i + 1:]
    raise AssertionError("nothing to corrupt")


@pytest.mark.parametrize("fact", ssf.COMMAND_FACTS, ids=lambda f: f.name)
def test_a_corrupted_command_is_still_captured_not_missed(fact):
    """The load-bearing design property.

    A pattern that hard-codes the command would not match a corrupted one, and the check would
    fail as "pattern not found" instead of a comparison naming both spellings. Anchored on the
    surrounding prose, the capture *survives* the corruption and it is the comparison that goes
    red — which is the error 验收 #1 asks for.
    """
    for surface in fact.surfaces():
        text = (REPO / surface.path).read_text(encoding="utf-8")
        match = surface.compiled().search(text)
        assert match, f"{fact.name} {surface.path}: the pattern stopped matching the tree"
        captured = match.group("cmd")
        corrupted = _flip_one_alnum(captured)
        assert corrupted != captured
        edited = text[: match.start("cmd")] + corrupted + text[match.end("cmd"):]
        again = surface.compiled().search(edited)
        assert again, (
            f"{fact.name} {surface.path}: a one-character corruption made the pattern miss "
            f"entirely — it hard-codes the command instead of capturing it"
        )
        assert again.group("cmd") == corrupted


# ── CI must run this gate ────────────────────────────────────────────────────────────────────────

def test_ci_runs_the_site_facts_check():
    """验收 #3: the new gate is wired where sync_lesson_count.py --check already runs."""
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        assert "sync_site_facts.py --check" in text, (
            f"{workflow.relative_to(REPO)} does not run scripts/sync_site_facts.py --check — "
            f"the gate exists only on a laptop until it is on the PR path"
        )


def test_the_checker_module_is_importable_without_side_effects():
    """importing must not rewrite anything; the CLI is the only writer."""
    assert callable(ssf.main) and callable(ssf.stale_entries_all)
    assert ssf.TOOL_SITES and ssf.COMMAND_FACTS
    assert all(isinstance(site, Site) for site in ssf.TOOL_SITES)
    # Every fact pairs at least the README source with the homepage mirror — the acceptance pair.
    for fact in ssf.COMMAND_FACTS:
        paths = {s.path for s in fact.surfaces()}
        assert "README.md" in paths and "docs/index.html" in paths, (fact.name, paths)
