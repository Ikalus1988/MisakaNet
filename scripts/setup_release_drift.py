#!/usr/bin/env python3
"""Is the published installer as fresh as the repository it is built from? (#3691)

The report this answers
-----------------------
`npm` had `@misaka-net/misakanet-setup` at **0.5.6** (published 2026-09-19) while the package's
source had moved **ten commits ahead** (the last change 2026-10-19). A new user running
`npx @misaka-net/misakanet-setup` got a month-old installer.

The report blamed "no publish automation". That was wrong: `.github/workflows/misakanet-setup-publish.yml`
has published the package on a `misakanet-setup-v*` tag since 0.2.0, and it does the right thing
with the tarball it builds. What was missing was the half *before* it — nothing ever bumped
`packages/misakanet-setup/package.json` and nothing ever created the tag, because
`release-please-config.json` declared **one** package (the repository root). The publish path was
fine and had nothing to publish.

`--verify` could not see the gap either, and still cannot: it compares against **npm latest**
(`latestPublishedVersion()` in the installer), and 0.5.6 *is* npm latest, so the only thing it can
report is "you are up to date". The gap is between the **registry** and the **repository**, and
that is what this script measures.

The two questions
-----------------
* **Did the last release reach npm?** The release tag says which version was released; the
  registry says whether anybody received it. A tag with no published version is a release that
  never happened.
* **Has the shipped source moved since that release?** The tarball is built from
  `packages/misakanet-setup` plus the hook and voice sources `scripts/copy-hook.mjs` copies in at
  pack time. If those files moved after the tag, the installer on npm is older than the
  repository.

One distinction keeps the second question honest. release-please bumps the version in a release
pull request, so a version that is declared but not tagged yet is a release **in flight**, not
drift — the release pull request must not be blocked by the gate that watches it. It becomes drift
when the release was cut days ago and still has no tag: then the publish path is broken, not the
release flow.

The grace period
----------------
The second question carries one on purpose. A release-please flow bumps the version *after* the
change lands, so "the source is ahead of the last release" is true for a few days **by design**.
It becomes drift when it *stays* that way: after `GRACE_DAYS` the release is late, and a late
release is a failure, not a warning. That is what makes the state this repository sat in — a
month — impossible to sit in again.

Exit codes, and they are not allowed to blur into one another (the same discipline as
`registry-drift-watch.yml`): **0** = no drift, **1** = drift, **2** = the question could not be
answered (npm was unreachable — that is *not* evidence that the listing is wrong).

Usage:
    python3 scripts/setup_release_drift.py --repo .
    python3 scripts/setup_release_drift.py --repo . --npm-versions 0.5.6 --now 2026-10-22T00:00:00+00:00
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

NPM_PACKAGE = "@misaka-net/misakanet-setup"
TAG_PREFIX = "misakanet-setup-v"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# The files the published tarball is built from: the package's own shipped files, plus the hook
# and voice sources `packages/misakanet-setup/scripts/copy-hook.mjs` copies in at pack time.
#
# The list is here rather than in the workflow because the workflow calls this module, and
# `tests/test_setup_release_automation.py` checks this list against the package's own
# declarations (`package.json`'s `files` and copy-hook.mjs's sources) — a file that is shipped but
# not watched here would be a hole in the gate, and the test is what keeps the list honest.
SHIPPED_SOURCES = (
    "packages/misakanet-setup/bin/misakanet-setup.mjs",
    "packages/misakanet-setup/README.md",
    "integrations/agent-autostart/checkpoint_reminder.mjs",
    "integrations/agent-autostart/voice_hook.mjs",
    "docs/assets/voice",
)

# How long the source may be ahead of the last release before the release counts as late.
GRACE_DAYS = 7.0


@dataclass
class Report:
    """The verdict, and the lines that say why."""

    status: str = "ok"  # "ok" | "drift" | "unknown"
    problems: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return {"ok": 0, "drift": 1, "unknown": 2}[self.status]


def git(repo: Path, *args: str) -> str:
    """One git command in `repo`. Raises on failure — a git failure is a broken comparison."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def version_key(raw: str) -> tuple[int, int, int] | None:
    """`X.Y.Z` as a sortable tuple, or None when the string is not a version."""
    match = SEMVER.match(raw.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def released_tags(repo: Path, prefix: str = TAG_PREFIX) -> list[tuple[tuple[int, int, int], str, str]]:
    """Every release tag as `(sort key, version, tag)`, oldest first.

    The tag is the repository's own record of what was released, so it is the base of the
    comparison — not the version in `package.json`, which is the version that is *about* to be
    released.
    """
    found = []
    for tag in git(repo, "tag", "-l", f"{prefix}*").split():
        raw = tag[len(prefix):]
        key = version_key(raw)
        if key:
            found.append((key, raw, tag))
    return sorted(found)


def published_versions(package: str = NPM_PACKAGE, injected: list[str] | None = None) -> list[str]:
    """Every version the registry has for the package.

    `injected` short-circuits the network call; the test uses it so that a synthetic repository
    can be measured without asking npm about a version that does not exist.
    """
    if injected is not None:
        return list(injected)
    url = "https://registry.npmjs.org/" + package.replace("/", "%2f")
    with urllib.request.urlopen(url, timeout=30) as response:
        return sorted(json.load(response)["versions"])


def shipped_drift(repo: Path, tag: str) -> tuple[list[str], datetime | None]:
    """The shipped files that moved after `tag`, and when the first of them moved.

    The date is the *oldest* unreleased change, not the newest: a release that is one day late
    because of a change from a month ago is a month late.
    """
    changed = git(repo, "diff", "--name-only", tag, "HEAD", "--", *SHIPPED_SOURCES).split()
    if not changed:
        return [], None
    log = git(
        repo, "log", "--format=%cI", "--reverse", f"{tag}..HEAD", "--", *SHIPPED_SOURCES
    ).splitlines()
    if not log:
        return sorted(changed), None
    moment = datetime.fromisoformat(log[0])
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return sorted(changed), moment


def declared_version(repo: Path) -> str | None:
    """The version `packages/misakanet-setup/package.json` declares.

    release-please owns that file: the version in it is the one that is *about* to be released,
    which is what tells a release in flight from a release that was never cut.
    """
    path = repo / "packages" / "misakanet-setup" / "package.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return None


def version_bumped_at(repo: Path, tag: str) -> datetime | None:
    """When the package's version was last bumped after `tag`."""
    log = git(
        repo, "log", "--format=%cI", "-1", f"{tag}..HEAD", "--",
        "packages/misakanet-setup/package.json",
    ).splitlines()
    if not log:
        return None
    moment = datetime.fromisoformat(log[0])
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def assess(
    repo: Path,
    *,
    published: list[str] | None = None,
    now: datetime | None = None,
    grace_days: float = GRACE_DAYS,
) -> Report:
    """Compare the published package with the repository. The whole decision, in one place."""
    report = Report()
    report.lines.append(f"setup-release-drift: {repo}")

    releases = released_tags(repo)
    if not releases:
        report.status = "drift"
        report.problems.append(
            f"the setup package has never been released (no {TAG_PREFIX}* tag)"
        )
        return report
    _, version, tag = releases[-1]
    report.lines.append(f"  last release tag : {tag}")

    try:
        versions = published_versions(injected=published)
    except Exception as error:  # noqa: BLE001 - the point is to report, not to raise
        report.status = "unknown"
        report.problems.append(f"could not ask npm for {NPM_PACKAGE}: {error}")
        return report
    report.lines.append(f"  npm has           : {', '.join(versions) if versions else '(nothing)'}")

    if version not in versions:
        report.problems.append(
            f"the release {tag} was tagged but npm has no {version} — the release never reached "
            "the registry"
        )

    moment = now or datetime.now(timezone.utc)
    declared = declared_version(repo)
    in_flight = bool(
        declared and version_key(declared) and version_key(declared) > version_key(version)
    )
    if in_flight:
        report.lines.append(
            f"  a release is cut  : {declared} (the package declares it; the tag has not been "
            "created yet)"
        )

    changed, oldest = shipped_drift(repo, tag)
    if changed:
        report.lines.append(f"  shipped source    : {len(changed)} file(s) moved after {tag}")
        for path in changed:
            report.lines.append(f"      {path}")
        if oldest is None:
            report.problems.append(
                f"the shipped source moved after {tag} and the age of the change could not be read"
            )
        else:
            age = (moment - oldest).total_seconds() / 86400.0
            bumped_at = version_bumped_at(repo, tag) if in_flight else None
            if in_flight and bumped_at is not None:
                # A release that has been cut and is on its way is not drift: the version was
                # bumped, the tag and the publish follow. It becomes drift when the release was
                # cut long enough ago that it should have been published by now — that is the
                # publish path being broken rather than the release flow.
                waiting = (moment - bumped_at).total_seconds() / 86400.0
                if waiting > grace_days:
                    report.problems.append(
                        f"the release {declared} was cut {waiting:.0f} days ago and still has no "
                        f"{TAG_PREFIX}{declared} tag — the publish path is broken"
                    )
                else:
                    report.lines.append(
                        f"  a release is due  : {declared} was cut {waiting:.0f} day(s) ago — "
                        "publish it"
                    )
            elif age > grace_days:
                report.problems.append(
                    f"the shipped source has been ahead of {tag} for {age:.0f} days "
                    f"(grace: {grace_days:.0f}) — a release is overdue"
                )
            else:
                report.lines.append(
                    f"  a release is due  : {age:.0f} of {grace_days:.0f} grace days used"
                )
    else:
        report.lines.append("  shipped source    : matches the release")

    if report.problems:
        report.status = "drift"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="the repository root (default: the cwd)")
    parser.add_argument(
        "--npm-versions",
        default=None,
        help="comma separated versions the registry has; skips the network call",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="ISO-8601 moment to measure the grace period against (default: now)",
    )
    parser.add_argument(
        "--grace-days",
        type=float,
        default=GRACE_DAYS,
        help=f"how long the source may be ahead of the last release (default: {GRACE_DAYS:.0f})",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    published = args.npm_versions.split(",") if args.npm_versions else None
    now = datetime.fromisoformat(args.now) if args.now else None

    report = assess(repo, published=published, now=now, grace_days=args.grace_days)
    for line in report.lines:
        print(line)
    for problem in report.problems:
        print(f"FAIL: {problem}")
    if report.status == "ok":
        print("OK: the published setup package is not behind the repository")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
