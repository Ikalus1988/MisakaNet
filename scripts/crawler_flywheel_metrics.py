#!/usr/bin/env python3
"""Read-only GitHub crawler-flywheel metrics for MisakaNet.

Tracks whether machine-readable issues/releases correlate with fork/PR flow.
Requires no token, but GH_TOKEN avoids low anonymous API limits.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone


UTC = timezone.utc


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def gh_json(url: str, token: str = ""):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "misakanet-crawler-flywheel-metrics",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise SystemExit(
                "GitHub API rate-limited. Set GH_TOKEN, then retry.\n"
                "PowerShell: $env:GH_TOKEN='<token>'"
            ) from exc
        raise


def gh_pages(base: str, token: str, pages: int = 3):
    out = []
    sep = "&" if "?" in base else "?"
    for page in range(1, pages + 1):
        data = gh_json(f"{base}{sep}per_page=100&page={page}", token)
        if not data:
            break
        out.extend(data)
        if len(data) < 100:
            break
    return out


def issue_refs(text: str) -> set[int]:
    return {int(n) for n in re.findall(r"#(\d+)", text or "")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute crawler/flywheel PR metrics")
    parser.add_argument("--repo", default="Ikalus1988/MisakaNet")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--pages", type=int, default=4)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", help="Append full JSON report to a JSONL file")
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN", "")
    api = f"https://api.github.com/repos/{args.repo}"
    cutoff = datetime.now(UTC) - timedelta(days=args.days)

    repo_info = gh_json(api, token)
    issues_raw = gh_pages(f"{api}/issues?state=all&sort=created&direction=desc", token, args.pages)
    pulls_raw = gh_pages(f"{api}/pulls?state=all&sort=created&direction=desc", token, args.pages)
    tags_raw = gh_pages(f"{api}/tags", token, 1)

    issues = {
        i["number"]: i
        for i in issues_raw
        if "pull_request" not in i and parse_dt(i["created_at"]) >= cutoff
    }
    pulls = [p for p in pulls_raw if parse_dt(p["created_at"]) >= cutoff]

    prs_by_issue: dict[int, list[dict]] = defaultdict(list)
    for pr in pulls:
        refs = issue_refs(pr.get("title", "")) | issue_refs(pr.get("body", ""))
        for n in refs:
            if n in issues:
                prs_by_issue[n].append(pr)

    issue_rows = []
    for n, issue in sorted(issues.items()):
        created = parse_dt(issue["created_at"])
        labels = [l["name"] for l in issue.get("labels", [])]
        prs = sorted(prs_by_issue.get(n, []), key=lambda p: parse_dt(p["created_at"]))
        merged = [p for p in prs if p.get("merged_at")]
        closed_unmerged = [p for p in prs if p.get("closed_at") and not p.get("merged_at")]
        first_pr_hours = None
        if prs:
            first_pr_hours = round((parse_dt(prs[0]["created_at"]) - created).total_seconds() / 3600, 2)
        competing_48h = sum(
            1 for p in prs if parse_dt(p["created_at"]) <= created + timedelta(hours=48)
        )
        stale_hits = sum(
            1
            for p in closed_unmerged
            if re.search(r"duplicate|supersed|stale|covered|conflict", (p.get("title", "") + "\n" + (p.get("body") or "")), re.I)
        )
        issue_rows.append(
            {
                "issue": n,
                "title": issue["title"],
                "created_at": issue["created_at"],
                "labels": labels,
                "pr_count": len(prs),
                "merged_prs": len(merged),
                "closed_unmerged_prs": len(closed_unmerged),
                "first_pr_hours": first_pr_hours,
                "competing_prs_48h": competing_48h,
                "comment_count": issue.get("comments", 0),
                "stale_scope_hits": stale_hits,
            }
        )

    label_perf = defaultdict(lambda: {"issues": 0, "prs": 0, "merged": 0, "competing48": 0})
    for row in issue_rows:
        for label in row["labels"]:
            label_perf[label]["issues"] += 1
            label_perf[label]["prs"] += row["pr_count"]
            label_perf[label]["merged"] += row["merged_prs"]
            label_perf[label]["competing48"] += row["competing_prs_48h"]

    pr_hours = Counter(parse_dt(p["created_at"]).hour for p in pulls)
    pr_days = Counter(parse_dt(p["created_at"]).date().isoformat() for p in pulls)
    releases = [
        {"name": t["name"], "zipball_url": t.get("zipball_url", "")}
        for t in tags_raw[:10]
    ]

    report = {
        "repo": args.repo,
        "generated_at": datetime.now(UTC).isoformat(),
        "window_days": args.days,
        "repo_metrics": {
            "stars": repo_info.get("stargazers_count"),
            "forks": repo_info.get("forks_count"),
            "watchers": repo_info.get("subscribers_count"),
            "open_issues": repo_info.get("open_issues_count"),
        },
        "summary": {
            "issues": len(issues),
            "pulls": len(pulls),
            "referenced_issues": sum(1 for r in issue_rows if r["pr_count"]),
            "total_issue_linked_prs": sum(r["pr_count"] for r in issue_rows),
            "total_merged_issue_linked_prs": sum(r["merged_prs"] for r in issue_rows),
            "avg_time_to_first_pr_hours": round(
                sum(r["first_pr_hours"] for r in issue_rows if r["first_pr_hours"] is not None)
                / max(1, sum(1 for r in issue_rows if r["first_pr_hours"] is not None)),
                2,
            ),
        },
        "issue_rows": sorted(issue_rows, key=lambda r: (r["pr_count"], r["competing_prs_48h"]), reverse=True),
        "label_perf": dict(sorted(label_perf.items(), key=lambda kv: kv[1]["prs"], reverse=True)),
        "pr_created_by_utc_hour": dict(sorted(pr_hours.items())),
        "pr_created_by_day": dict(sorted(pr_days.items())),
        "recent_tags": releases,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.save:
            with open(args.save, "a", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        return 0

    if args.save:
        with open(args.save, "a", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")

    s = report["summary"]
    print("# Crawler Flywheel Metrics")
    print(f"repo: {args.repo} | window: {args.days}d | generated: {report['generated_at']}")
    print()
    print("## Summary")
    print(f"- issues: {s['issues']}")
    print(f"- PRs: {s['pulls']}")
    print(f"- issue-linked PRs: {s['total_issue_linked_prs']} ({s['total_merged_issue_linked_prs']} merged)")
    print(f"- avg time to first PR: {s['avg_time_to_first_pr_hours']}h")
    print(f"- stars/forks/watchers: {repo_info.get('stargazers_count')}/{repo_info.get('forks_count')}/{repo_info.get('subscribers_count')}")
    print()
    print("## Top crawler-attracting issues")
    for r in report["issue_rows"][:10]:
        print(
            f"- #{r['issue']} PRs={r['pr_count']} merged={r['merged_prs']} "
            f"48h={r['competing_prs_48h']} first={r['first_pr_hours']}h "
            f"labels={','.join(r['labels'][:4])} :: {r['title'][:90]}"
        )
    print()
    print("## Top labels by PR pull")
    for label, v in list(report["label_perf"].items())[:12]:
        print(f"- {label}: issues={v['issues']} PRs={v['prs']} merged={v['merged']} 48h={v['competing48']}")
    print()
    print("## PR creation UTC hours")
    print(", ".join(f"{h}:00={c}" for h, c in report["pr_created_by_utc_hour"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
