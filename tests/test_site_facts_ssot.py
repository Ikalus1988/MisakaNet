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
machinery ``scripts/sync_lesson_count.py`` uses. These tests pin three properties:

1. the gate is green on the tree as committed;
2. it can go red, and a red run names **both** files with their lines — the reader needs to see
   the two spellings side by side, not only which one "won";
3. the capture patterns are anchored on the surrounding prose rather than on the command text,
   which is the only reason a corrupted command is *captured and compared* instead of silently
   reported as "pattern not found".
"""
from __future__ import annotations

import shutil
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


# ── and it can go red, naming both files ─────────────────────────────────────────────────────────

def _mini_tree(tmp_path: Path) -> Path:
    """A root with just the two surfaces a command fact reads.

    Copying the real files keeps the patterns honest — a fixture that this file also wrote would
    pass even if the patterns matched nothing in the repository.
    """
    (tmp_path / "docs").mkdir()
    shutil.copy(REPO / "README.md", tmp_path / "README.md")
    shutil.copy(REPO / "docs" / "index.html", tmp_path / "docs" / "index.html")
    return tmp_path


def test_a_one_character_corruption_on_the_homepage_names_both_files(tmp_path):
    """验收 #1: change one character of the install command → the check fails citing both files.

    The error must carry both paths and both spellings — a message that says only "drift" sends
    the reader hunting, which is half of why this went unnoticed for so long.
    """
    root = _mini_tree(tmp_path)
    index = root / "docs" / "index.html"
    text = index.read_text(encoding="utf-8")
    old = '<div class="qs-cmd">npx @misaka-net/misakanet-setup</div>'
    new = '<div class="qs-cmd">npx @misaka-net/misakanet-setuq</div>'
    assert text.count(old) == 1, "the homepage install command moved — update this test with it"
    index.write_text(text.replace(old, new, 1), encoding="utf-8")

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
    old = '<div class="qs-cmd">npx @misaka-net/misakanet-setup</div>'
    index.write_text(
        text.replace(old, '<div class="qs-cmd">npx @misaka-net/misakanet-setuq</div>', 1),
        encoding="utf-8",
    )

    changes, errors = ssf.sync_command_facts(root=root)
    assert errors == [], errors
    assert changes, "the corrupted mirror was not rewritten"
    assert ssf.stale_command_entries(root=root) == []
    assert "npx @misaka-net/misakanet-setup</div>" in index.read_text(encoding="utf-8")
    assert "setuq" not in index.read_text(encoding="utf-8")


def test_the_tool_count_site_rewrites_again_on_a_second_run(tmp_path):
    """The lesson-count write-once bug, pinned for this row: a second run must rewrite again.

    Driven through ``sync_all`` (the machinery ``sync_tool_count`` delegates to) with an explicit
    count, because ``canonical_mcp_tools`` measures the real AGENTS.md/worker pair and has no
    meaning inside a fixture tree.
    """
    (tmp_path / "docs").mkdir()
    target = tmp_path / "docs" / "index.html"
    target.write_text("shows misakanet with 7 tools", encoding="utf-8")

    changes, errors = sync_all(8, root=tmp_path, sites=ssf.TOOL_SITES, write_count_file=False)
    assert errors == [], errors
    assert changes, "the stale count was not rewritten"
    assert target.read_text(encoding="utf-8") == "shows misakanet with 8 tools"

    changes, errors = sync_all(9, root=tmp_path, sites=ssf.TOOL_SITES, write_count_file=False)
    assert errors == [], errors
    assert changes, "a second sync with a different count found nothing to rewrite (write-once)"
    assert target.read_text(encoding="utf-8") == "shows misakanet with 9 tools"


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
