"""
Tests for Changelog Generator (scripts/gen_changelog.py)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.gen_changelog import (
    categorize_pr,
    generate_changelog_section,
    update_changelog_file,
)


def test_categorize_pr():
    assert categorize_pr("feat(search): add preflight inspection") == "Features"
    assert categorize_pr("feat: add new lesson") == "Features"
    assert categorize_pr("fix(mcp): resolve path traversal in loader") == "Fixes"
    assert categorize_pr("hotfix: secret redaction") == "Fixes"
    assert categorize_pr("docs: update README with quickstart") == "Documentation"
    assert categorize_pr("test(ci): add unit tests for tokenizer") == "Testing & Benchmarks"
    assert categorize_pr("bench: add memory benchmark") == "Testing & Benchmarks"
    assert categorize_pr("chore(deps): bump actions/checkout") == "Maintenance & Chores"
    assert categorize_pr("style: format code with black") == "Maintenance & Chores"
    assert categorize_pr("random unformatted PR title") == "Other Changes"


def test_generate_changelog_section():
    mock_prs = [
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
        release_tag="v2.18.0",
        release_name="v2.18.0 — Automation Release",
        release_date="2026-08-15T20:00:00Z",
        prs=mock_prs,
    )

    assert "## v2.18.0 — Automation Release — 2026-08-15" in section
    assert "### Features" in section
    assert "- #101: feat(dx): auto changelog script (@ghzhost)" in section
    assert "### Fixes" in section
    assert "- #102: fix(ledger): prevent markdown injection (@ghzhost)" in section
    assert "### Documentation" in section
    assert "- #103: docs: add guide for contributors (@alice)" in section
    assert "### Maintenance & Chores" in section
    assert "- #104: chore(deps): bump node version (@dependabot[bot])" in section
    assert "### Contributors" in section
    assert "@alice" in section
    assert "@ghzhost" in section
    contrib_section = section.split("### Contributors")[-1]
    assert "@dependabot[bot]" not in contrib_section


def test_update_changelog_file(tmp_path: Path):
    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text(
        "# Misaka Network — Changelog\n\n## v2.17.0 — 2026-08-13\n\n- Existing item\n",
        encoding="utf-8",
    )

    new_section = (
        "## v2.18.0 — 2026-08-15\n\n### Features\n\n- #101: new feat\n\n---\n"
    )

    update_changelog_file(changelog_file, new_section, prepend=True)

    content = changelog_file.read_text(encoding="utf-8")
    assert content.index("## v2.18.0") < content.index("## v2.17.0")
    assert "- #101: new feat" in content
    assert "- Existing item" in content
