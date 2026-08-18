#!/usr/bin/env python3
"""Maintainer review queue — compact view of pending MCP intake issues.

Usage:
    python3 scripts/maintainer_review_queue.py [--repo OWNER/REPO] [--format text|json|markdown]
    python3 scripts/maintainer_review_queue.py --pending-only
    python3 scripts/maintainer_review_queue.py --action-stats

Read-only. Never closes, publishes, or modifies issues.

Shows:
    - Issue number, title, source, classification labels
    - Dedup hash (if available)
    - Suggested action: convert-to-lesson / needs-info / close-as-noise / merge-duplicate
    - Separates: intake-test, lesson candidates, vague/noise
"""
import argparse
import json
import hashlib
import subprocess
import sys
from collections import Counter, defaultdict

REPO_DEFAULT = "Ikalus1988/MisakaNet"

INTAKE_LABELS = {"intake", "mcp-intake", "pending-review"}
LESSON_LABELS = {"lesson-candidate", "enhancement"}
TEST_LABELS = {"intake-test", "status:competition"}
NOISE_LABELS = {"noise", "spam", "invalid"}


def gh_issue_list(repo, state="open", labels=None, limit=100):
    """List issues via gh CLI."""
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", state, "--limit", str(limit),
           "--json", "number,title,labels,assignees,createdAt,body"]
    if labels:
        cmd += ["--label", ",".join(labels)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return []
    return json.loads(result.stdout)


def extract_labels(issue):
    """Extract label names as a set."""
    return {l["name"] for l in issue.get("labels", [])}


def dedup_hash(issue):
    """Generate dedup hash from title + body."""
    text = (issue.get("title", "") or "") + (issue.get("body", "") or "")
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:12]


def suggest_action(issue, labels):
    """Suggest maintainer action based on labels and content."""
    if labels & NOISE_LABELS:
        return "close-as-noise"
    if "intake-test" in labels:
        return "review-test-data"
    if labels & LESSON_LABELS and "ready" in labels:
        return "convert-to-lesson"
    if "needs-ac" in labels:
        return "needs-acceptance-criteria"
    if "needs-dco" in labels:
        return "request-dco-signoff"
    title = (issue.get("title", "") or "").lower()
    if any(kw in title for kw in ["test", "spam", "dummy", "foo", "bar"]):
        return "likely-noise"
    body = issue.get("body", "") or ""
    if len(body) < 50:
        return "needs-info"
    return "review-manually"


def categorize_issue(labels, title):
    """Categorize issue into queue buckets."""
    if labels & TEST_LABELS:
        return "intake-test"
    if labels & LESSON_LABELS:
        return "lesson-candidate"
    if "pool:quick" in labels:
        return "quick-task"
    if "pool:deep" in labels:
        return "deep-task"
    if any(kw in title.lower() for kw in ["bounty", "reward"]):
        return "bounty"
    return "unclassified"


def format_text(issues):
    """Format as human-readable text."""
    by_category = defaultdict(list)
    for issue in issues:
        labels = extract_labels(issue)
        cat = categorize_issue(labels, issue.get("title", ""))
        action = suggest_action(issue, labels)
        by_category[cat].append((issue, labels, action))

    lines = []
    for cat in ["lesson-candidate", "quick-task", "deep-task", "intake-test", "bounty", "unclassified"]:
        items = by_category.get(cat, [])
        if not items:
            continue
        lines.append(f"\n{'='*60}")
        lines.append(f"  {cat.upper().replace('-', ' ')} ({len(items)} issues)")
        lines.append(f"{'='*60}")
        for issue, labels, action in items:
            num = issue["number"]
            title = issue["title"][:70]
            lines.append(f"  #{num}  {title}")
            lines.append(f"        -> {action}")
            assigned = [a["login"] for a in issue.get("assignees", [])]
            if assigned:
                lines.append(f"        assigned: {', '.join(assigned)}")

    lines.append(f"\n{'-'*60}")
    lines.append(f"  Total: {len(issues)} open issues in queue")
    stats = Counter(categorize_issue(extract_labels(i), i.get("title", "")) for i in issues)
    for cat, count in stats.most_common():
        lines.append(f"    {cat}: {count}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Maintainer review queue for MCP intake issues")
    parser.add_argument("--repo", default=REPO_DEFAULT)
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--pending-only", action="store_true")
    parser.add_argument("--action-stats", action="store_true")
    args = parser.parse_args()

    issues = gh_issue_list(args.repo, labels=["good first issue"], limit=50)
    intake_issues = gh_issue_list(args.repo, labels=["mcp-intake"], limit=50)
    seen = {i["number"] for i in issues}
    for ii in intake_issues:
        if ii["number"] not in seen:
            issues.append(ii)
            seen.add(ii["number"])

    if args.pending_only:
        issues = [i for i in issues if not i.get("assignees")]

    if args.format == "json":
        output = []
        for issue in issues:
            labels = extract_labels(issue)
            output.append({
                "number": issue["number"],
                "title": issue["title"],
                "category": categorize_issue(labels, issue["title"]),
                "action": suggest_action(issue, labels),
                "dedup_hash": dedup_hash(issue),
                "labels": sorted(labels),
                "assigned": [a["login"] for a in issue.get("assignees", [])],
            })
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(format_text(issues))

    if args.action_stats:
        actions = Counter(suggest_action(i, extract_labels(i)) for i in issues)
        print(f"\nAction distribution:")
        for action, count in actions.most_common():
            print(f"  {action}: {count}")


if __name__ == "__main__":
    main()
