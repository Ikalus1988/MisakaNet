#!/usr/bin/env python3
"""The installer's release body — rendered by the shared renderer in `scripts/release_notes.py`.

Why this file still exists (2026-10-25, #3836)
----------------------------------------------
`misakanet-setup-publish.yml` calls this path
(`python3 ../../scripts/setup_release_notes.py --version "$VERSION"`), and the installer keeps its
own entry point. What used to live here — the two heading shapes release-please writes, the section
cut, the `npx` footer — now lives in `scripts/release_notes.py`, which the root package's tag job
calls too. Two release lines, one renderer.

That matters because the two lines used to ship *different notes for the same kind of release*:
this entry point shipped the CHANGELOG's `### Bug Fixes` categories, while the root package shipped
a flat `## What's Changed` PR list from `--generate-notes`. See `scripts/release_notes.py` for the
numbers.

The history below is the installer's, and it is why the fallback must not fail: it runs *after*
`npm publish`.

Every `misakanet-setup-v*` tag was a tag and nothing else: measured 2026-10-23, the last 100
GitHub Releases contained **zero** `misakanet-setup-*` entries, and

    gh release view misakanet-setup-v0.6.0   ->  release not found

The installer's version was visible on npm, in this package's CHANGELOG and in `--version`, but
never on the Releases page — the one page a reader opens to answer "what is the newest installer,
and what changed". The body is the package's own CHANGELOG section for that version, not
`--generate-notes`: the section is what release-please wrote for exactly this release, and
generating from commits is the shape that once listed 33 of 104 entries twice
(`tests/test_changelog_shape.py`).

Usage:
    python3 scripts/setup_release_notes.py --version 0.6.1
    python3 scripts/setup_release_notes.py --version 0.6.1 --changelog /tmp/CHANGELOG.md

Exit codes: **0** printed notes (a missing section still prints a fallback and warns on stderr),
**2** there is no changelog to read.
"""
from __future__ import annotations

import sys
from pathlib import Path

# `scripts/` on the path, whichever directory this file is invoked from: the setup publish workflow
# runs it as `../../scripts/setup_release_notes.py` from the package directory, and the tests import
# it after adding `scripts/` themselves.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import release_notes  # noqa: E402

PACKAGE = release_notes.SETUP.distribution
DEFAULT_CHANGELOG = release_notes.SETUP.changelog
DEFAULT_REPOSITORY = release_notes.DEFAULT_REPOSITORY
HEADING = release_notes.HEADING

section = release_notes.section


def render(changelog: str, version: str, repository: str = DEFAULT_REPOSITORY) -> str:
    """The installer's release body: the shared renderer, pinned to the setup package."""
    return release_notes.render(release_notes.SETUP, changelog, version, repository)


def main(argv: list[str] | None = None) -> int:
    """The installer's CLI; `--package` is pinned so the existing call site stays valid."""
    return release_notes.main(argv, default_package="setup")


if __name__ == "__main__":
    sys.exit(main())
