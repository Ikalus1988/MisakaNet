#!/usr/bin/env python3
"""The setup package's Release body comes from the CHANGELOG, not from the commit log.

Why this file exists (2026-10-23)
---------------------------------
Every `misakanet-setup-v*` tag was a tag and nothing else: the last 100 GitHub Releases carried
**zero** `misakanet-setup-*` entries, and `gh release view misakanet-setup-v0.6.0` answered
"release not found". npm was the only place the installer's version appeared, so the Releases page
showed nothing while the root package had a release per release.

`scripts/setup_release_notes.py` renders that missing body from the package's own CHANGELOG
section — the section release-please wrote for exactly that version, rather than a commit-generated
list (`tests/test_changelog_shape.py` exists because that list once repeated 33 of 104 entries).
These assertions pin the two properties the workflow relies on: the section stops at the next
version, and a missing section still produces a body after the publish has already succeeded.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import setup_release_notes as notes  # noqa: E402

CHANGELOG = REPO / "packages" / "misakanet-setup" / "CHANGELOG.md"

SYNTHETIC = """# Changelog

## 0.7.0 (2026-11-01)


### Features

* **setup:** the newer thing

## 0.6.0 (2026-10-22)


### Bug Fixes

* **setup:** the older thing

## 0.5.6 (2026-09-19)


### Bug Fixes

* **setup:** the oldest thing
"""

# release-please's other heading shape: once a previous tag exists to link against, it writes
# `## [version](compare-url) (date)`. The first real release after `setup_release_notes.py`
# shipped used exactly this, and the body fell back to "no section" (#0.7.0).
BRACKETED = """# Changelog

## [0.7.0](https://github.com/owner/repo/compare/misakanet-setup-v0.6.0...misakanet-setup-v0.7.0) (2026-10-24)


### Features

* **setup:** the newer linked thing

## [0.6.0](https://github.com/owner/repo/compare/misakanet-setup-v0.5.6...misakanet-setup-v0.6.0) (2026-10-22)


### Bug Fixes

* **setup:** the older linked thing
"""


def test_the_section_stops_at_the_next_version():
    body = notes.section(SYNTHETIC, "0.6.0")
    assert body.startswith("## 0.6.0 (2026-10-22)")
    assert "older thing" in body
    assert "newer thing" not in body, "the section leaked the version above it"
    assert "oldest thing" not in body, "the section leaked the version below it"


def test_a_missing_section_is_empty_not_the_whole_changelog():
    assert notes.section(SYNTHETIC, "9.9.9") == ""
    assert notes.section(SYNTHETIC, "0.6") == "", "a partial version must not match a heading"


def test_a_linked_heading_from_release_please_is_read():
    """The shape release-please switches to once a previous tag exists (the 0.7.0 Release)."""
    body = notes.section(BRACKETED, "0.6.0")
    assert body.startswith("## [0.6.0]")
    assert "older linked thing" in body
    assert "newer linked thing" not in body, "the section leaked the version above it"


def test_the_real_070_release_section_is_read():
    """The live changelog, because that is the file the first failing Release used."""
    body = notes.section(CHANGELOG.read_text(encoding="utf-8"), "0.7.0")
    assert body.startswith("## [0.7.0]"), body.splitlines()[0] if body else "MISSING"
    assert "add MiniMax Code (mcode) as a plugin target" in body


def test_the_real_060_section_is_the_one_that_shipped():
    """The live file, not a fixture: the release for 0.6.0 is the case that had no Release."""
    body = notes.section(CHANGELOG.read_text(encoding="utf-8"), "0.6.0")
    assert body.startswith("## 0.6.0 (2026-10-22)")
    assert "the install says what it is about to write" in body


def test_render_adds_the_way_to_get_it_and_to_check_it():
    body = notes.render(SYNTHETIC, "0.6.0", repository="owner/repo")
    assert "## 0.6.0 (2026-10-22)" in body
    assert "https://www.npmjs.com/package/@misaka-net/misakanet-setup/v/0.6.0" in body
    assert "https://github.com/owner/repo/blob/main/packages/misakanet-setup/CHANGELOG.md" in body
    assert "npx @misaka-net/misakanet-setup" in body
    assert "npx @misaka-net/misakanet-setup --verify" in body


def test_a_missing_version_still_renders_and_says_so_on_stderr(capsys):
    """The workflow runs this *after* `npm publish`: a missing section must not fail the publish."""
    code = notes.main(["--version", "9.9.9", "--changelog", str(CHANGELOG)])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "Release `@misaka-net/misakanet-setup@9.9.9`" in captured.out
    assert "WARN" in captured.err
    assert "9.9.9" in captured.out


def test_a_missing_changelog_is_an_error_not_an_empty_release(tmp_path, capsys):
    code = notes.main(["--version", "0.6.0", "--changelog", str(tmp_path / "nope.md")])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "FAIL" in captured.err
