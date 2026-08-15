#!/usr/bin/env python3
"""
MisakaNet Changelog Generator
=============================
Auto-generates markdown changelog from merged PRs between releases.

Usage:
  python3 scripts/gen_changelog.py [--from-tag v2.16.0] [--to-tag v2.17.0] [--output CHANGELOG.md] [--append]
  python3 scripts/gen_changelog.py --release-tag v2.17.0 --release-name "v2.17.0 — Trust & Curation Hardening"
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_DEFAULT = "Ikalus1988/MisakaNet"
CATEGORIES = [
    ("Features", ["feat", "feature"]),
    ("Fixes", ["fix", "bugfix", "hotfix"]),
    ("Documentation", ["docs", "doc"]),
    ("Testing & Benchmarks", ["test", "tests", "bench", "benchmark"]),
    ("Refactor & Performance", ["refactor", "perf", "performance"]),
    ("CI / DX & Tooling", ["ci", "dx", "build", "tooling", "tools"]),
    ("Maintenance & Chores", ["chore", "style", "deps", "data"]),
]


def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    token_file = Path.home() / ".config" / "github" / "token"
    if token_file.exists():
        try:
            return token_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


def github_request(url: str, token: str = "") -> dict | list:
    headers = {"User-Agent": "MisakaNet-Changelog-Generator", "Accept": "application/vnd.github.v3+json"}
    if not token:
        token = get_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_tag_info(repo: str, tag_name: str, token: str = "") -> dict:
    """Fetch tag commit date or release date."""
    # First check releases
    try:
        url = f"https://api.github.com/repos/{repo}/releases/tags/{urllib.parse.quote(tag_name)}"
        release = github_request(url, token=token)
        if isinstance(release, dict) and "published_at" in release:
            return {
                "name": tag_name,
                "date": release["published_at"],
                "release_name": release.get("name", tag_name),
            }
    except Exception:
        pass

    # Fallback to tag commit
    try:
        url = f"https://api.github.com/repos/{repo}/git/ref/tags/{urllib.parse.quote(tag_name)}"
        ref_data = github_request(url, token=token)
        sha = ref_data["object"]["sha"]
        commit_url = f"https://api.github.com/repos/{repo}/commits/{sha}"
        commit_data = github_request(commit_url, token=token)
        commit_date = commit_data["commit"]["committer"]["date"]
        return {
            "name": tag_name,
            "date": commit_date,
            "release_name": tag_name,
        }
    except Exception as e:
        raise RuntimeError(f"Could not find tag info for {tag_name}: {e}")


def get_merged_prs_between(repo: str, since_iso: str = "", until_iso: str = "", token: str = "") -> list[dict]:
    """Fetch merged PRs within a date range."""
    merged_prs = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/repos/{repo}/pulls?state=closed&per_page={per_page}&page={page}"
        try:
            items = github_request(url, token=token)
            if not items or not isinstance(items, list):
                break

            for pr in items:
                merged_at = pr.get("merged_at")
                if not merged_at:
                    continue

                if since_iso and merged_at < since_iso:
                    # Beyond since window, but wait: PRs are sorted by created_at desc, not merged_at desc
                    # We continue check until page is empty or 5 pages inspected
                    pass
                
                if since_iso and merged_at < since_iso:
                    continue
                if until_iso and merged_at > until_iso:
                    continue

                merged_prs.append(pr)

            if len(items) < per_page or page >= 10:
                break
            page += 1
        except Exception as e:
            print(f"Error fetching PRs page {page}: {e}", file=sys.stderr)
            break

    # Sort merged_prs by merged_at asc
    merged_prs.sort(key=lambda x: x["merged_at"])
    return merged_prs


def categorize_pr(title: str) -> str:
    """Categorize PR title using conventional commits prefix."""
    # Match prefixes like feat(scope): or fix: or docs:
    m = re.match(r"^([a-zA-Z0-9_-]+)(?:\([^\)]+\))?!?:\s*(.+)$", title.strip())
    prefix = ""
    if m:
        prefix = m.group(1).lower()
    else:
        # Check first word
        words = re.split(r"[\s:]+", title.strip())
        if words:
            prefix = words[0].lower()

    for cat_name, aliases in CATEGORIES:
        if prefix in aliases:
            return cat_name

    return "Other Changes"


def generate_changelog_section(
    release_tag: str,
    release_name: str,
    release_date: str,
    prs: list[dict],
) -> str:
    """Generate formatted markdown for a release section."""
    lines = []
    title_line = f"## {release_name or release_tag}"
    if release_date:
        date_str = release_date[:10]
        if not (release_name and date_str in release_name):
            title_line += f" — {date_str}"

    lines.append(title_line)
    lines.append("")

    if not prs:
        lines.append("_No pull requests recorded for this release._")
        lines.append("")
        return "\n".join(lines)

    # Group PRs by category
    categorized: dict[str, list[dict]] = {}
    for pr in prs:
        cat = categorize_pr(pr.get("title", ""))
        categorized.setdefault(cat, []).append(pr)

    # Collect contributors
    contributors = set()
    for pr in prs:
        user = pr.get("user", {})
        login = user.get("login")
        if login and not login.endswith("[bot]"):
            contributors.add(login)

    # Output categories in defined order
    for cat_name, _ in CATEGORIES:
        if cat_name in categorized:
            lines.append(f"### {cat_name}")
            lines.append("")
            for pr in categorized[cat_name]:
                num = pr["number"]
                title = pr.get("title", "").strip()
                user = pr.get("user", {}).get("login", "unknown")
                lines.append(f"- #{num}: {title} (@{user})")
            lines.append("")

    if "Other Changes" in categorized:
        lines.append("### Other Changes")
        lines.append("")
        for pr in categorized["Other Changes"]:
            num = pr["number"]
            title = pr.get("title", "").strip()
            user = pr.get("user", {}).get("login", "unknown")
            lines.append(f"- #{num}: {title} (@{user})")
        lines.append("")

    # Contributors section
    if contributors:
        lines.append("### Contributors")
        lines.append("")
        contrib_list = ", ".join(f"@{c}" for c in sorted(contributors, key=lambda s: s.lower()))
        lines.append(f"Thank you to all contributors: {contrib_list}")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def update_changelog_file(filepath: Path, new_section: str, prepend: bool = True):
    """Write or update CHANGELOG.md."""
    if not filepath.exists():
        header = "# Misaka Network — Changelog\n\n> `Lessons learned. Lessons shared.`\n> Cross-agent lesson sync via Git.\n\nAll notable changes to the Misaka Network project are documented here.\n\n---\n\n"
        filepath.write_text(header + new_section, encoding="utf-8")
        return

    content = filepath.read_text(encoding="utf-8")
    
    # Check if section already exists
    first_line = new_section.strip().split("\n")[0]
    if first_line in content:
        print(f"Section '{first_line}' already present in {filepath}, updating...", file=sys.stderr)
        # We can replace the section or keep it
        # If it matches ## v..., replace until next ##
        pattern = re.escape(first_line) + r".*?(?=\n## |\Z)"
        content = re.sub(pattern, new_section.strip() + "\n\n", content, flags=re.DOTALL)
        filepath.write_text(content, encoding="utf-8")
        return

    if prepend:
        # Find where the first '## ' section starts
        idx = content.find("## ")
        if idx != -1:
            updated = content[:idx] + new_section + "\n" + content[idx:]
        else:
            updated = content + "\n\n" + new_section
        filepath.write_text(updated, encoding="utf-8")
    else:
        filepath.write_text(content + "\n\n" + new_section, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Auto-generate changelog from merged PRs.")
    parser.add_argument("--repo", default=REPO_DEFAULT, help="GitHub repository (owner/repo)")
    parser.add_argument("--from-tag", default="", help="Starting tag/release (exclusive)")
    parser.add_argument("--to-tag", default="", help="Ending tag/release (inclusive)")
    parser.add_argument("--release-tag", default="", help="Release tag name (e.g. v2.17.0)")
    parser.add_argument("--release-name", default="", help="Release display name")
    parser.add_argument("--since", default="", help="ISO datetime filter start")
    parser.add_argument("--until", default="", help="ISO datetime filter end")
    parser.add_argument("--output", default="", help="Output changelog path (e.g. CHANGELOG.md)")
    parser.add_argument("--stdout", action="store_true", help="Print changelog section to stdout")
    parser.add_argument("--token", default="", help="GitHub Personal Access Token")

    args = parser.parse_args()

    token = args.token or get_github_token()
    since_date = args.since
    until_date = args.until
    release_name = args.release_name or args.release_tag or args.to_tag or "Unreleased"

    if args.from_tag and not since_date:
        tag_info = get_tag_info(args.repo, args.from_tag, token=token)
        since_date = tag_info["date"]

    if args.to_tag and not until_date:
        tag_info = get_tag_info(args.repo, args.to_tag, token=token)
        until_date = tag_info["date"]
        if not args.release_name:
            release_name = tag_info.get("release_name", args.to_tag)

    if not until_date:
        until_date = datetime.now(timezone.utc).isoformat()

    print(f"Fetching merged PRs for {args.repo} from {since_date or 'beginning'} to {until_date}...", file=sys.stderr)
    prs = get_merged_prs_between(args.repo, since_iso=since_date, until_iso=until_date, token=token)
    print(f"Found {len(prs)} merged PR(s).", file=sys.stderr)

    section = generate_changelog_section(
        release_tag=args.release_tag or args.to_tag or "vNext",
        release_name=release_name,
        release_date=until_date,
        prs=prs,
    )

    if args.stdout or not args.output:
        print(section)

    if args.output:
        out_path = Path(args.output)
        update_changelog_file(out_path, section, prepend=True)
        print(f"Updated {out_path} with {len(prs)} PR entries.", file=sys.stderr)


if __name__ == "__main__":
    main()
