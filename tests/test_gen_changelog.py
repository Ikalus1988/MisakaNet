#!/usr/bin/env python3
"""Tests for Changelog Generator (scripts/gen_changelog.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gen_changelog import (
    categorise,
    categorize_pr,
    format_entry,
    generate_changelog,
    generate_changelog_section,
    update_changelog_file,
)


def test_categorize_pr():
    assert categorize_pr("feat(search): add preflight inspection") == "Added"
    assert categorize_pr("feat: add new lesson") == "Added"
    assert categorize_pr("fix(mcp): resolve path traversal in loader") == "Fixed"
    assert categorize_pr("fix: secret redaction") == "Fixed"
    assert categorize_pr("docs: update README with quickstart") == "Documentation"
    assert categorize_pr("test(ci): add unit tests for tokenizer") == "Tests"
    assert categorize_pr("ci: add memory benchmark") == "Tests"
    assert categorize_pr("chore(deps): bump actions/checkout") == "Maintenance"
    assert categorize_pr("style: format code with black") == "Changed"
    assert categorize_pr("random unformatted PR title") == "Other"


def test_categorise():
    pr = {"title": "feat(mcp): add register tool", "labels": []}
    assert categorise(pr) == "Added"

    pr = {"title": "Fix search bug", "labels": [{"name": "bug"}]}
    assert categorise(pr) == "Fixed"

    pr = {"title": "Random title", "labels": []}
    assert categorise(pr) == "Other"


def test_format_entry():
    pr = {"title": "feat(mcp): add register tool", "number": 1212}
    entry = format_entry(pr)
    assert "#1212" in entry
    assert "add register tool" in entry


def test_generate_changelog():
    prs = [
        {"title": "feat(mcp): add register tool", "number": 1212, "labels": []},
        {"title": "fix(worker): resolve ReferenceError", "number": 1186, "labels": []},
        {"title": "docs(readme): deduplicate curl", "number": 1195, "labels": []},
    ]
    changelog = generate_changelog(prs)
    assert "### Added" in changelog
    assert "### Fixed" in changelog
    assert "### Documentation" in changelog
    assert "#1212" in changelog
    assert "#1186" in changelog


def test_generate_changelog_section():
    prs = [
        {
            "number": 101,
            "title": "feat(dx): auto changelog script",
            "user": {"login": "ghzhost"},
        },
        {
            "number": 102,
            "title": "fix(ledger): prevent markdown injection",
            "user": {"login": "ghzhost"},
        },
        {
            "number": 103,
            "title": "docs: add guide for contributors",
            "user": {"login": "alice"},
        },
        {
            "number": 104,
            "title": "chore(deps): bump node version",
            "user": {"login": "dependabot[bot]"},
        },
    ]

    section = generate_changelog_section(
        release_tag="v2.19.0",
        release_name="v2.19.0 — Automation Release",
        release_date="2026-08-22T20:00:00Z",
        prs=prs,
    )

    assert "## v2.19.0 — Automation Release — 2026-08-22" in section
    assert "### Added" in section
    assert "#101" in section
    assert "### Fixed" in section
    assert "#102" in section
    assert "### Documentation" in section
    assert "#103" in section
    assert "### Contributors" in section
    assert "@alice" in section
    assert "@ghzhost" in section
    # Bot should not appear in contributors
    contrib_section = section.split("### Contributors")[-1]
    assert "@dependabot[bot]" not in contrib_section


def test_update_changelog_file_prepend(tmp_path):
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text(
        "# Misaka Network — Changelog\n\n## v2.17.0 — 2026-08-13\n\n- Existing item\n",
        encoding="utf-8",
    )

    new_section = "## v2.18.0 — 2026-08-22\n\n### Added\n\n- #101: new feat\n\n---\n"
    update_changelog_file(changelog_file, new_section, prepend=True)

    result = changelog_file.read_text(encoding="utf-8")
    assert "v2.18.0" in result
    assert "v2.17.0" in result
    # v2.18.0 should come before v2.17.0
    assert result.index("v2.18.0") < result.index("v2.17.0")


def test_update_changelog_file_append(tmp_path):
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text(
        "# Misaka Network — Changelog\n\n## v2.17.0\n\n- Existing\n",
        encoding="utf-8",
    )

    new_section = "## v2.18.0\n\n### Added\n\n- #101: new feat\n"
    update_changelog_file(changelog_file, new_section, prepend=False)

    result = changelog_file.read_text(encoding="utf-8")
    assert "v2.18.0" in result
    assert result.index("v2.17.0") < result.index("v2.18.0")
