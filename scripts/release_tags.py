#!/usr/bin/env python3
"""Which merged package releases are still missing their tag.

Why this exists (#4031)
-----------------------
`release-please.yml` tags the **root** package and nothing else: it reads `manifest['.']`, pushes
`v<version>`, and dispatches `release-pypi.yml`. The manifest has declared `packages/misakanet-setup`
and `packages/fatal-guard` for a while, so:

* no `fatal-guard-v<version>` tag was ever created, and `fatal-guard-publish.yml` — which listens for
  exactly that tag — never fired;
* no npm workflow was dispatched at all.

Measured 2026-10-29: shipping `fatal-guard@0.3.1` needed a tag pushed by hand, and again for 0.3.2.
While a merged release sits untagged, release-please also reads it as outstanding and proposes the same
commit range again (that is where the duplicate 0.3.3 PR came from).

What it prints
--------------
One line per merged, untagged package release:

    <tag> <component> <version> <publish-workflow-or-empty>

`<publish-workflow>` is `<component>-publish.yml` when that file exists — the convention both package
workflows already follow — and empty when there is none, which the caller must handle rather than
guess.

The tag name is computed from `release-please-config.json`, not from a literal: `component` +
`tag-separator` + `v` + version, which is release-please's own `TagName.toString()`. A second spelling
of that rule would eventually disagree with the release PRs it is meant to complete.

Usage
-----
    python3 scripts/release_tags.py              # human-readable
    python3 scripts/release_tags.py --lines      # `tag component version workflow` per line
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "release-please-config.json"
MANIFEST = REPO / ".release-please-manifest.json"
WORKFLOWS = REPO / ".github" / "workflows"


def tag_for(block: dict, version: str) -> str:
    """release-please's tag for one package: `component<sep>v<version>`."""
    separator = block.get("tag-separator", "-")
    component = block["component"]
    return f"{component}{separator}v{version}"


def existing_tags(repo: Path = REPO) -> set[str] | None:
    """Every local tag, or None when this checkout has none (a shallow clone cannot tell)."""
    result = subprocess.run(["git", "tag", "--list"], cwd=repo, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    tags = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return tags or None


def pending(repo: Path = REPO) -> list[dict]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tags = existing_tags(repo)
    rows = []
    for path, version in sorted(manifest.items()):
        if path == ".":
            continue                      # the root release has its own step, with its own rules
        block = config.get("packages", {}).get(path)
        if not block or not block.get("component"):
            continue
        tag = tag_for(block, version)
        if tags is not None and tag in tags:
            continue
        workflow = f"{block['component']}-publish.yml"
        rows.append({
            "path": path,
            "component": block["component"],
            "version": version,
            "tag": tag,
            "workflow": workflow if (WORKFLOWS / workflow).exists() else "",
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lines", action="store_true",
                    help="print `tag component version workflow` for shell consumption")
    args = ap.parse_args(argv)

    rows = pending()
    if args.lines:
        for row in rows:
            print(f"{row['tag']} {row['component']} {row['version']} {row['workflow']}")
        return 0

    if not rows:
        print("every declared package release is tagged")
        return 0
    print(f"{len(rows)} package release(s) merged and not tagged:")
    for row in rows:
        publishes = f"publishes via {row['workflow']}" if row["workflow"] else "no publish workflow found"
        print(f"  {row['tag']:28s} {row['version']:10s} {publishes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
