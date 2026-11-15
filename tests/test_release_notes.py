#!/usr/bin/env python3
"""The Release body is the CHANGELOG section — for the product package and the installer alike.

Why this file exists (2026-10-25, #3836)
----------------------------------------
`gh release view v2.50.1 --json body | grep -cE '^### (Bug Fixes|Features|Lessons|Tests)'` answered
**0**. The root package's tag job used `gh release create --generate-notes`, so the page a reader
opens to decide whether to upgrade showed a flat `## What's Changed` PR list, while the
`CHANGELOG.md` next to it carried the categories release-please maintains. The installer had already
been fixed (`scripts/setup_release_notes.py`, #3795 / #3803); the product package was the same
problem, with no renderer at all.

`scripts/release_notes.py` is now the one renderer both lines use. These tests pin what the Release
page must contain (the section, and its `### <category>` headings), the two heading shapes
release-please writes — the second is the one #3803 fixed — and the workflow wiring that calls it,
so the two lines cannot drift back into two dialects.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import release_notes  # noqa: E402

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow")

WORKFLOW = REPO / ".github" / "workflows" / "release-please.yml"
CHANGELOG = REPO / "CHANGELOG.md"
MANIFEST = REPO / ".release-please-manifest.json"
CONFIG = REPO / "release-please-config.json"

# release-please's shape once a previous tag exists to link against — the one #3803 fixed for the
# installer line, and the only shape the root changelog has used since release-please took it over.
LINKED = """# Changelog

## [2.50.1](https://github.com/owner/repo/compare/v2.50.0...v2.50.1) (2026-10-25)


### Bug Fixes

* **deps:** clear the filelock alerts ([#3825](https://github.com/owner/repo/issues/3825))

## [2.50.0](https://github.com/owner/repo/compare/v2.49.0...v2.50.0) (2026-10-24)


### Features

* **setup:** the older thing
"""

# The other shape: no previous tag to link to, so release-please writes a bare version.
PLAIN = """# Changelog

## 2.50.1 (2026-10-25)


### Features

* **site:** the newer thing

## 2.50.0 (2026-10-24)


### Bug Fixes

* **site:** the older thing
"""

# v3.17.1 (2026-11-15) as it actually shipped: one merged pull request, `lessons(contrib)`, so the
# section carries `### Lessons` and nothing else. Copy of the live shape, not a hypothetical — the
# release PR that carried it was red on `test_the_rendered_root_body_carries_the_changelog_categories`
# for ten hours because that assertion named two categories by hand.
LESSONS_ONLY = """# Changelog

## [3.17.1](https://github.com/owner/repo/compare/v3.17.0...v3.17.1) (2026-11-15)


### Lessons

* **contrib:** convert five intakes — Douyin dead-end, ROBOGUIDE wedge ([#5031](https://github.com/owner/repo/issues/5031)) ([50a9eb5](https://github.com/owner/repo/commit/50a9eb5))

## [3.17.0](https://github.com/owner/repo/compare/v3.16.0...v3.17.0) (2026-11-15)


### Features

* **analytics:** record where a search spends its milliseconds ([#4948](https://github.com/owner/repo/issues/4948))
"""

# What the root changelog looked like before release-please owned it
# (`grep -n '^## v' CHANGELOG.md`).
LEGACY = """# Changelog

## v2.18.0 — 2026-08-21

### Bug Fixes

* the hand-written entry

## v2.17.1 — 2026-08-16

* the older hand-written entry
"""


def test_the_linked_heading_release_please_writes_is_read():
    body = release_notes.section(LINKED, "2.50.1")
    assert body.startswith("## [2.50.1]"), body.splitlines()[0] if body else "MISSING"
    assert "### Bug Fixes" in body
    assert "the older thing" not in body, "the section leaked the version below it"


def test_the_unlinked_heading_release_please_writes_is_read():
    body = release_notes.section(PLAIN, "2.50.1")
    assert body.startswith("## 2.50.1 (2026-10-25)")
    assert "### Features" in body
    assert "the older thing" not in body, "the section leaked the version below it"


def test_the_legacy_hand_written_heading_is_read():
    """A backfill of an old root tag must read its section, not claim none exists."""
    body = release_notes.section(LEGACY, "2.18.0")
    assert body.startswith("## v2.18.0")
    assert "the hand-written entry" in body
    assert "the older hand-written entry" not in body, "the section leaked the version below it"


def test_a_partial_version_does_not_match_a_heading():
    assert release_notes.section(LINKED, "2.50") == ""
    assert release_notes.section(LINKED, "9.9.9") == ""


def _assert_reads_as_categories(body: str, version: str) -> list[str]:
    """#3836's rule, in the shape it has to be written: categories — whose, not which.

    The assertion this replaced named `### Bug Fixes` / `### Features` by hand. v3.17.1 was
    lessons-only, so on 2026-11-15 the release PR that carried it was red on all nine legs plus
    `audit` for ten hours — while the tag job's own live check (`grep -qE '^### '`) and the workflow
    gate that reads the published body back were both green. A release whose only section is
    `### Lessons` is a normal release here: `lesson` and `lessons` are two of the eight sections
    this repository configures.

    What the rule must still catch is the defect itself: no category at all, or headings that came
    from somewhere other than this repository's config.
    """
    headings = re.findall(r"^### (.+)$", body, re.M)
    assert headings, f"the release body for {version} has no `### <category>` heading"
    assert "What's Changed" not in body, (
        "this is the `--generate-notes` shape #3836 is about: a flat PR list with no categories"
    )

    configured = {
        section["section"]
        for section in json.loads(CONFIG.read_text(encoding="utf-8"))["packages"]["."][
            "changelog-sections"
        ]
    }
    assert configured & set(headings), (
        f"the body's headings {headings} are not the categories this repository configures "
        f"({sorted(configured)}), so the section was probably read from the wrong place"
    )
    return headings


def test_the_rendered_root_body_carries_the_changelog_categories():
    """The defect (#3836) on the live files: the body must show the categories, not a PR list."""
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["."]
    body = release_notes.render(release_notes.ROOT, CHANGELOG.read_text(encoding="utf-8"), version)
    _assert_reads_as_categories(body, version)


def test_a_release_whose_only_commit_was_a_lesson_is_still_a_release():
    """v3.17.1, replayed: `### Lessons` alone satisfies the rule; naming categories does not."""
    body = release_notes.render(release_notes.ROOT, LESSONS_ONLY, "3.17.1", "owner/repo")
    assert _assert_reads_as_categories(body, "3.17.1") == ["Lessons"]
    assert "the older thing" not in body, "the section leaked the version below it"


def test_a_body_with_no_category_is_still_rejected():
    """The negative half, so relaxing the pair above cannot quietly drop #3836's rule."""
    flat = "## [3.17.1](https://example/compare) (2026-11-15)\n\n## What's Changed\n* a PR\n"
    with pytest.raises(AssertionError, match="no `### <category>` heading"):
        _assert_reads_as_categories(flat, "3.17.1")


def test_a_body_built_from_another_repositorys_categories_is_rejected():
    """Read the wrong section and the headings say so: they are not this repo's vocabulary."""
    foreign = (
        "## [3.17.1](https://example/compare) (2026-11-15)\n\n"
        "### Added\n\n* keep-a-changelog calls it `Added`\n"
    )
    with pytest.raises(AssertionError, match="not the categories this repository configures"):
        _assert_reads_as_categories(foreign, "3.17.1")


def test_the_root_body_says_where_to_get_that_version():
    body = release_notes.render(release_notes.ROOT, LINKED, "2.50.1", "owner/repo")
    assert body.startswith("## [2.50.1]")
    assert "**PyPI:** https://pypi.org/project/misakanet/2.50.1/" in body
    assert "**changelog:** https://github.com/owner/repo/blob/main/CHANGELOG.md" in body
    assert "pip install misakanet==2.50.1" in body


def test_a_missing_section_still_renders_a_body():
    """The tag is already pushed when this runs: a release with a fallback body beats no release."""
    body = release_notes.render(release_notes.ROOT, LINKED, "9.9.9")
    assert "Release `misakanet@9.9.9`" in body
    assert "no `## 9.9.9` section in `CHANGELOG.md`" in body


def test_both_lines_render_through_the_same_function():
    """#3836's second criterion: one renderer, so a heading-shape fix reaches both lines."""
    import setup_release_notes

    text = CHANGELOG.read_text(encoding="utf-8")
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["."]
    assert setup_release_notes.render(text, version, "owner/repo") == release_notes.render(
        release_notes.SETUP, text, version, "owner/repo"
    )
    assert setup_release_notes.section is release_notes.section


def test_the_cli_prints_the_body_for_the_package_it_is_told_to_render(capsys):
    code = release_notes.main(
        ["--package", "root", "--version", "2.50.1", "--changelog", str(CHANGELOG)]
    )
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "### Bug Fixes" in captured.out
    assert captured.err == ""


def test_without_a_package_the_cli_refuses_to_guess():
    """A wrong package is a wrong body; the shared CLI must not default to one line."""
    with pytest.raises(SystemExit) as raised:
        release_notes.main(["--version", "2.50.1"])
    assert raised.value.code == 2


def test_a_missing_changelog_is_an_error_not_an_empty_release(tmp_path, capsys):
    code = release_notes.main(
        ["--package", "root", "--version", "2.50.1", "--changelog", str(tmp_path / "nope.md")]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "FAIL" in captured.err


# ── the workflow wiring ──────────────────────────────────────────────────────────────────────────
def _release_steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["release"]["steps"]


def _step(name: str) -> dict:
    step = next((s for s in _release_steps() if s.get("name") == name), None)
    assert step is not None, f"release-please.yml lost its `{name}` step"
    return step


def _commands(run: str) -> str:
    """The shell lines of a step, minus comments.

    A comment that names a flag is not an invocation of it."""
    return "\n".join(line for line in run.splitlines() if not line.lstrip().startswith("#"))


def test_the_tag_job_renders_the_body_from_the_changelog():
    tag = next(s for s in _release_steps() if s.get("id") == "release_tag")
    run = str(tag.get("run", ""))
    commands = _commands(run)
    assert "gh release create" in commands
    assert "--generate-notes" not in commands, (
        "`--generate-notes` builds a flat PR list from the commit range; the body must be the "
        "CHANGELOG section (#3836)"
    )
    assert "scripts/release_notes.py --package root" in commands, (
        "the root line must render through the same renderer as the installer line"
    )
    assert "--notes-file" in commands, (
        "the rendered body must be what `gh release create` publishes"
    )
    assert (REPO / "scripts" / "release_notes.py").is_file(), (
        "the step calls a script that does not exist"
    )
    assert run.index('git tag "$TAG"') < run.index("gh release create"), (
        "the tag has to exist before the Release is created from it"
    )


def test_the_footer_check_does_not_collide_with_changelog_text():
    """The body is now the CHANGELOG, so the old `misakanet-setup` marker can appear in the body."""
    tag = next(s for s in _release_steps() if s.get("id") == "release_tag")
    commands = _commands(str(tag.get("run", "")))
    assert 'grep -q "misakanet-setup"' not in commands, (
        "an entry that mentions the installer would make the step think the footer is already there"
    )
    assert "MARKER=" in commands, "the marker must come from the footer itself"


def test_the_tag_job_reads_the_published_body_back():
    """The issue's `gh release view … --json body` check, as a warning rather than a gate."""
    step = _step("Check the release body carries the CHANGELOG categories")
    run = str(step.get("run", ""))
    assert "gh release view" in run and "--json body" in run, (
        "the check must read the artifact a reader sees, not the file it came from"
    )
    assert "grep -qE '^### '" in run, "the check must look for a category heading"
    assert "::warning::" in run
    assert "exit 1" not in run, (
        "the Release already exists at this point; failing would skip the PyPI/npm dispatches"
    )
    assert step.get("if") == "steps.release_tag.outputs.created == 'true'"
