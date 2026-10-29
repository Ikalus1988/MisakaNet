#!/usr/bin/env python3
"""One renderer for both release lines: the GitHub Release body is the CHANGELOG section.

Why this exists (2026-10-25, #3836)
-----------------------------------
The repository maintains two release lines and, until this file, two dialects of release notes.

`scripts/setup_release_notes.py` rendered the installer's body from
`packages/misakanet-setup/CHANGELOG.md` (#3795, heading shapes fixed in #3803). The root package's
tag job rendered nothing: `gh release create "$TAG" --generate-notes` asked GitHub for a body, and
GitHub builds that from the commit range — a flat `## What's Changed` list of PR titles.

Measured on v2.50.1:

    gh release view v2.50.1 --json body --jq .body \
      | grep -cE '^### (Bug Fixes|Features|Lessons|Tests)'
    0

while `CHANGELOG.md`'s section for that same version carried four of those headings. The notes are
the one page a reader opens to decide whether to upgrade, and the categories were the one thing they
did not show. There is no second implementation here to drift.

What it reads
-------------
The section release-please wrote for exactly this version, heading included, so the compare link
survives. Both heading shapes must be read; the second is the one #3803 fixed (the bracket was
absent from the pattern and the 0.7.0 installer Release fell back to "no section"):

    ## 0.6.0 (2026-10-22)                                       # no previous tag to link to
    ## [0.7.0](https://…/compare/misakanet-setup-v0.6.0…0.7.0) (2026-10-24)

The root CHANGELOG also carries pre-release-please headings (`## v2.18.0 — 2026-08-21`) from before
release-please owned the file. They are accepted too, so a backfill reads the section instead of
claiming none exists; historical tags are not backfilled automatically
(`docs/release-checklist.md`).

Exit codes: **0** printed notes (a missing section still prints a fallback and warns on stderr),
**2** there is no changelog to read. The fallback is deliberate and is the installer line's existing
contract: the renderer runs *after* a package was published, and a red step there would mark a
successful publish as broken. The root line's step runs after the tag was pushed, where a failure
would leave a tag with no Release at all.

Usage:
    python3 scripts/release_notes.py --package root  --version 2.50.1
    python3 scripts/release_notes.py --package setup --version 0.7.1

`scripts/setup_release_notes.py` is the installer's entry point into this module, kept because
`misakanet-setup-publish.yml` calls that path.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_REPOSITORY = "Ikalus1988/MisakaNet"

# Two release-please shapes, plus the hand-written `## v2.18.0 — 2026-08-21` headings that predate
# release-please's ownership of the root changelog. A partial version must not match a heading
# (`2.50` against `## [2.50.1]`), hence the lookahead after the full `X.Y.Z`.
HEADING = re.compile(
    r"^##\s+\[?v?(?P<version>\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\]?(?=[\s(—–-])"
)


@dataclass(frozen=True)
class Package:
    """One release line: where its changelog lives, and how a reader gets that version."""

    key: str
    distribution: str
    ecosystem: str
    changelog: Path
    changelog_path: str  # repo-relative, for the link in the body
    release_url: str  # `{version}` substituted
    install: tuple[str, ...] = ()  # `{version}` substituted


ROOT = Package(
    key="root",
    distribution="misakanet",
    ecosystem="PyPI",
    changelog=REPO / "CHANGELOG.md",
    changelog_path="CHANGELOG.md",
    release_url="https://pypi.org/project/misakanet/{version}/",
    install=("pip install misakanet=={version}",),
)

SETUP = Package(
    key="setup",
    distribution="@misaka-net/misakanet-setup",
    ecosystem="npm",
    changelog=REPO / "packages" / "misakanet-setup" / "CHANGELOG.md",
    changelog_path="packages/misakanet-setup/CHANGELOG.md",
    release_url="https://www.npmjs.com/package/@misaka-net/misakanet-setup/v/{version}",
    install=(
        "npx @misaka-net/misakanet-setup",
        "npx @misaka-net/misakanet-setup --verify",
    ),
)

FATAL_GUARD = Package(
    key="fatal-guard",
    distribution="@misaka-net/fatal-guard",
    ecosystem="npm",
    changelog=REPO / "packages" / "fatal-guard" / "CHANGELOG.md",
    changelog_path="packages/fatal-guard/CHANGELOG.md",
    release_url="https://www.npmjs.com/package/@misaka-net/fatal-guard/v/{version}",
    install=(
        "npx @misaka-net/fatal-guard -- <your-command>",
    ),
)

PACKAGES = {package.key: package for package in (ROOT, SETUP, FATAL_GUARD)}


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


def render(
    package: Package,
    changelog: str,
    version: str,
    repository: str = DEFAULT_REPOSITORY,
) -> str:
    """The release body: the changelog section, then how to get it and how to check it."""
    body = section(changelog, version)
    if not body:
        body = (
            f"Release `{package.distribution}@{version}` — this version has no `## {version}` "
            f"section in `{package.changelog_path}`."
        )
    lines = [
        body,
        "",
        f"**{package.ecosystem}:** {package.release_url.format(version=version)}",
        f"**changelog:** https://github.com/{repository}/blob/main/{package.changelog_path}",
        "",
    ]
    if package.install:
        lines += [
            "```bash",
            *(command.format(version=version) for command in package.install),
            "```",
            "",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None, default_package: str | None = None) -> int:
    """Render one package's release body to stdout.

    `default_package` is what the package-specific entry point (`setup_release_notes.py`) pins;
    without it `--package` is required, so a caller can never silently render the wrong line.
    """
    parser = argparse.ArgumentParser(
        description="Render a GitHub Release body from the CHANGELOG section for one version."
    )
    parser.add_argument(
        "--package",
        choices=sorted(PACKAGES),
        default=default_package,
        required=default_package is None,
        help="the release line to render (default: whatever the entry point pins)",
    )
    parser.add_argument("--version", required=True, help="the version the release is for")
    parser.add_argument(
        "--changelog",
        default=None,
        help="the CHANGELOG to read (default: the one the package is defined by)",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
        help="owner/repo for the changelog link (default: $GITHUB_REPOSITORY or this repository)",
    )
    args = parser.parse_args(argv)

    package = PACKAGES[args.package]
    path = Path(args.changelog) if args.changelog else package.changelog
    if not path.is_file():
        print(f"FAIL: no changelog at {path}", file=sys.stderr)
        return 2
    changelog = path.read_text(encoding="utf-8")
    if not section(changelog, args.version):
        print(
            f"WARN: no `## {args.version}` section in {path}; the release body will say so",
            file=sys.stderr,
        )
    sys.stdout.write(render(package, changelog, args.version, args.repository))
    return 0


if __name__ == "__main__":
    sys.exit(main())
