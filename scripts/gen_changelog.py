#!/usr/bin/env python3
"""Changelog Generator — Issue #1054.

Auto-generates changelog entries from merged PRs since a given date/tag.
Categorises by conventional commit prefix or labels.

Usage:
    python3 scripts/gen_changelog.py                          # since last tag
    python3 scripts/gen_changelog.py --since 2025-01-01       # since date
    python3 scripts/gen_changelog.py --version 2.16.0         # tag the release
    python3 scripts/gen_changelog.py --dry-run                # preview only
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

CATEGORY_MAP = {
    "feat": "Added", "add": "Added", "new": "Added", "introduce": "Added",
    "fix": "Fixed", "bugfix": "Fixed", "patch": "Fixed", "resolve": "Fixed",
    "refactor": "Changed", "improve": "Changed", "enhance": "Changed", "update": "Changed",
    "perf": "Changed", "optim": "Changed", "style": "Changed",
    "docs": "Documentation", "doc": "Documentation", "readme": "Documentation",
    "test": "Tests", "ci": "Tests", "chore": "Maintenance", "build": "Maintenance",
    "revert": "Reverted",
}

LABEL_MAP = {
    "bug": "Fixed", "enhancement": "Added", "feature": "Added",
    "documentation": "Documentation", "test": "Tests",
    "breaking": "Breaking Changes", "maintenance": "Maintenance",
}


def get_last_tag(repo):
    try:
        r = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=repo, timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def get_merged_prs(repo, since_date=None, owner=None, repo_name=None):
    since = since_date or "2020-01-01"
    query = f"merged:>={since}"
    cmd = [
        "gh", "pr", "list",
        "--repo", f"{owner}/{repo_name}",
        "--search", f"merged:>={since}",
        "--state", "merged",
        "--json", "number,title,labels,mergedAt,body",
        "--limit", "200",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=repo, timeout=60)
        if r.returncode != 0:
            print(f"Warning: gh pr list failed: {r.stderr.strip()}", file=sys.stderr)
            return []
        return json.loads(r.stdout)
    except FileNotFoundError:
        print("Error: 'gh' CLI not found. Install with: brew install gh", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching PRs: {e}", file=sys.stderr)
        return []


def categorise(pr):
    title = pr.get("title", "")
    match = re.match(r"^(\w+)[(!:]", title)
    if match:
        prefix = match.group(1).lower()
        if prefix in CATEGORY_MAP:
            return CATEGORY_MAP[prefix]

    labels = [l.get("name", "").lower() for l in pr.get("labels", [])]
    for label in labels:
        if label in LABEL_MAP:
            return LABEL_MAP[label]

    return "Other"


def format_entry(pr):
    title = pr.get("title", "")
    cleaned = re.sub(r"^\w+[(!:]\s*", "", title).strip()
    number = pr.get("number", "?")
    return f"- {cleaned} (#{number})"


def generate_changelog(prs):
    categories = defaultdict(list)
    for pr in prs:
        cat = categorise(pr)
        entry = format_entry(pr)
        categories[cat].append(entry)

    order = [
        "Breaking Changes", "Added", "Fixed", "Changed",
        "Documentation", "Tests", "Maintenance", "Reverted", "Other",
    ]
    lines = []
    for cat in order:
        entries = categories.get(cat, [])
        if not entries:
            continue
        entries.sort()
        lines.append(f"### {cat}\n")
        lines.extend(entries)
        lines.append("")

    for cat in sorted(categories.keys()):
        if cat not in order and categories[cat]:
            lines.append(f"### {cat}\n")
            lines.extend(sorted(categories[cat]))
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate changelog from merged PRs")
    parser.add_argument("--repo", default="Ikalus1988/MisakaNet")
    parser.add_argument("--since", help="PR merge date (YYYY-MM-DD)")
    parser.add_argument("--version", help="Version tag (e.g. 2.16.0)")
    parser.add_argument("--output", type=str, help="Output file path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    owner, repo_name = args.repo.split("/")
    since = args.since
    if not since:
        tag = get_last_tag(Path(__file__).resolve().parent.parent)
        if tag:
            print(f"Last tag: {tag}")
            since = re.sub(r"[^0-9\-]", "", tag.replace("v", ""))
            if len(since) < 10:
                since = f"{since}-01-01"
        else:
            since = "2025-01-01"
        print(f"Fetching PRs merged since {since}")

    prs = get_merged_prs(
        str(Path(__file__).resolve().parent.parent),
        since_date=since, owner=owner, repo_name=repo_name,
    )
    print(f"Found {len(prs)} merged PRs")

    if not prs:
        print("No PRs found. Check --repo and --since values.")
        return

    changelog = generate_changelog(prs)

    if args.version:
        header = f"## [{args.version}] — {datetime.now().strftime('%Y-%m-%d')}\n\n"
        changelog = header + changelog

    if args.dry_run:
        print("\n--- DRY RUN ---\n")
        print(changelog)
        return

    output = Path(args.output) if args.output else Path(__file__).resolve().parent.parent / "CHANGELOG-GENERATED.md"
    output.write_text(changelog, encoding='utf-8')
    print(f"Changelog written to {output}")
    print(f"Categories: {len([l for l in changelog.split(chr(10)) if l.startswith('### ')])}")


if __name__ == "__main__":
    main()
