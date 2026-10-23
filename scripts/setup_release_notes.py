#!/usr/bin/env python3
"""Render the GitHub Release notes for one `@misaka-net/misakanet-setup` version.

Why this exists (2026-10-23)
----------------------------
Every `misakanet-setup-v*` tag was a tag and nothing else: measured that day, the last 100
GitHub Releases contained **zero** `misakanet-setup-*` entries, and

    gh release view misakanet-setup-v0.6.0   ->  release not found

The installer's version was visible on npm, in this package's CHANGELOG and in `--version`, but
never on the Releases page — the one page a reader opens to answer "what is the newest installer,
and what changed". The root package has had a Release per release all along; the installer had
none, because its tag job only tags and dispatches the npm publish.

The body is the package's own CHANGELOG section for that version, not `--generate-notes`: the
section is what release-please wrote for exactly this release, and generating from commits is the
shape that once listed 33 of 104 entries twice (`tests/test_changelog_shape.py`).

Usage:
    python3 scripts/setup_release_notes.py --version 0.6.1
    python3 scripts/setup_release_notes.py --version 0.6.1 --changelog /tmp/CHANGELOG.md

Exit codes: **0** printed notes (a missing section still prints a fallback and warns on stderr),
**2** there is no changelog to read. It must not fail on a missing section: this runs *after*
`npm publish`, and a red step there would mark a successful publish as broken. The missing section
is a release-flow defect that release-please prevents by construction (it writes the section when
it bumps the version); the warning is what makes it visible instead of silent.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = "@misaka-net/misakanet-setup"
DEFAULT_CHANGELOG = REPO / "packages" / "misakanet-setup" / "CHANGELOG.md"
DEFAULT_REPOSITORY = "Ikalus1988/MisakaNet"
HEADING = re.compile(r"^##\s+(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\s")


def section(text: str, version: str) -> str:
    """The `## <version>` block, up to the next `## ` heading (or EOF). Empty when absent."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match and match.group("version") == version:
            start = index
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def render(changelog: str, version: str, repository: str = DEFAULT_REPOSITORY) -> str:
    """The release body: the changelog section, then how to get it and how to check it."""
    body = section(changelog, version)
    if not body:
        body = (
            f"Release `{PACKAGE}@{version}` — this version has no `## {version}` section in "
            "`packages/misakanet-setup/CHANGELOG.md`."
        )
    return "\n".join(
        [
            body,
            "",
            f"**npm:** https://www.npmjs.com/package/{PACKAGE}/v/{version}",
            f"**changelog:** https://github.com/{repository}/blob/main/packages/misakanet-setup/CHANGELOG.md",
            "",
            "```bash",
            "npx @misaka-net/misakanet-setup",
            "npx @misaka-net/misakanet-setup --verify",
            "```",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the release notes for one @misaka-net/misakanet-setup version."
    )
    parser.add_argument("--version", required=True, help="the version the release is for")
    parser.add_argument(
        "--changelog",
        default=str(DEFAULT_CHANGELOG),
        help="the package CHANGELOG to read (default: the one in this checkout)",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
        help="owner/repo for the changelog link (default: $GITHUB_REPOSITORY or this repository)",
    )
    args = parser.parse_args(argv)

    path = Path(args.changelog)
    if not path.is_file():
        print(f"FAIL: no changelog at {path}", file=sys.stderr)
        return 2
    changelog = path.read_text(encoding="utf-8")
    if not section(changelog, args.version):
        print(
            f"WARN: no `## {args.version}` section in {path}; the release body will say so",
            file=sys.stderr,
        )
    sys.stdout.write(render(changelog, args.version, args.repository))
    return 0


if __name__ == "__main__":
    sys.exit(main())
