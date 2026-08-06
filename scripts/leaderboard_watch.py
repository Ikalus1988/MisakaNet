#!/usr/bin/env python3
"""
Leaderboard Watcher — 贡献榜变化检测与通知

在每次 main 分支更新时运行，计算当前贡献排行榜，
与上次快照对比，如果榜首发生变化则创建通知 Issue。

用法:
    python3 scripts/leaderboard_watch.py              # 正常运行（环境变量 GH_TOKEN 需设置）
    python3 scripts/leaderboard_watch.py --dry-run    # 只打印不写入

环境变量:
    GH_TOKEN: GitHub Personal Access Token
    GH_REPO:  repo 名（默认 Ikalus1988/MisakaNet）
"""
from __future__ import annotations

import json
import os
import sys
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REPO = os.environ.get("GH_REPO", "Ikalus1988/MisakaNet")
TOKEN = os.environ.get("GH_TOKEN", "")
DRY_RUN = "--dry-run" in sys.argv

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "lessons"
LEADERBOARD_FILE = REPO_ROOT / "data" / "leaderboard.json"
META_FILE = REPO_ROOT / "data" / "leaderboard_meta.json"

GRAPHQL_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              oid
              committedDate
              author { user { login } name }
            }
          }
        }
      }
    }
  }
}
"""


def gh_api(method="GET", path="", data=None, graphql=None):
    """调用 GitHub API"""
    if graphql:
        url = "https://api.github.com/graphql"
        body = json.dumps({"query": graphql, "variables": {
            "owner": REPO.split("/")[0],
            "repo": REPO.split("/")[1],
        }}).encode()
    else:
        url = f"https://api.github.com/{path}"
        body = json.dumps(data).encode() if data else None

    headers = {
        "Authorization": f"token {TOKEN}",
        "User-Agent": "misakanet-leaderboard-bot",
        "Accept": "application/vnd.github.v3+json",
    }
    req = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(req) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None


def _fetch_merged_prs(owner: str, repo: str) -> list[dict]:
    """Fetch all merged PRs via REST, paginated. Returns list of PR dicts."""
    prs = []
    page = 1
    while page <= 10:  # max 1000 PRs
        data = gh_api("GET", f"repos/{owner}/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100&page={page}")
        if not data:
            break
        batch = [pr for pr in data if pr.get("merged_at")]
        prs.extend(batch)
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.3)
    return prs


def _pr_size_factor(additions: int, deletions: int) -> float:
    """Log-scaled PR size factor. 1-line fix → ~0.3, 100-line PR → ~1.0, 1000-line → ~1.5."""
    import math
    total = max(1, additions + deletions)
    return math.log10(total) + 1  # log10(1)+1=1.0, log10(100)+1=3.0 → normalize


def _recency_bonus(days_ago: int) -> float:
    """Separate recency bonus: recent activity gets extra boost."""
    if days_ago <= 7:
        return 0.5
    if days_ago <= 30:
        return 0.2
    return 0.0


def compute_leaderboard():
    """从 GitHub API 获取贡献数据，计算排行榜

    评分公式:
        commit_score = time_decay(days_ago) * pr_size_factor(additions, deletions)
        total = sum(commit_scores) + lessons_bonus + recency_bonus

    时间衰减: 30天半衰期，最低 10% (contributions never fully expire)
    PR 大小: log10(lines_changed) + 1 (1行修复 vs 1000行特性有区分)
    续期加成: 7天内 +0.5, 30天内 +0.2 (单独于衰减)
    """
    owner, repo = REPO.split("/")
    print("Fetching commit history via GraphQL...")
    contrib = {}  # login → list of {days_ago, commit_count}
    cursor = None
    page = 0

    while page < 20:  # 最多 20 页 = 2000 commits
        page += 1
        query = """
        query {
          repository(owner: "%s", name: "%s") {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100, %s) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                      oid
                      committedDate
                      author { user { login } name }
                    }
                  }
                }
              }
            }
          }
        }
        """ % (owner, repo, f'after: "{cursor}"' if cursor else "")

        body = json.dumps({"query": query}).encode()
        url = "https://api.github.com/graphql"
        req = Request(url, data=body, method="POST", headers={
            "Authorization": f"token {TOKEN}",
            "User-Agent": "misakanet-leaderboard-bot",
        })
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read())
        except HTTPError as e:
            print(f"  GraphQL HTTP {e.code}: {e.read().decode()[:200]}")
            break

        if "errors" in data:
            print(f"  GraphQL error: {data['errors']}")
            break

        try:
            history = data["data"]["repository"]["defaultBranchRef"]["target"]["history"]
        except (TypeError, KeyError):
            print("  Failed to parse GraphQL response")
            break

        for node in history["nodes"]:
            if not node:
                continue
            author = node.get("author", {}) or {}
            login = (author.get("user") or {}).get("login") or author.get("name") or "unknown"
            login = login.lower()
            ts = node.get("committedDate", "")

            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                days_ago = (datetime.now(timezone.utc) - dt).days
            except (ValueError, AttributeError):
                days_ago = 365

            if login not in contrib:
                contrib[login] = []
            contrib[login].append(days_ago)

        if not history["pageInfo"]["hasNextPage"]:
            break
        cursor = history["pageInfo"]["endCursor"]
        time.sleep(0.5)  # 限速保护

    # Fetch merged PRs for size factor
    print("Fetching merged PRs for size factor...")
    prs = _fetch_merged_prs(owner, repo)
    # Build per-author PR size data: login → list of (days_ago, additions, deletions)
    pr_by_author = {}
    now = datetime.now(timezone.utc)
    for pr in prs:
        login = (pr.get("user") or {}).get("login", "unknown").lower()
        merged_at = pr.get("merged_at", "")
        try:
            dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            days_ago = (now - dt).days
        except (ValueError, AttributeError):
            days_ago = 365
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)
        if login not in pr_by_author:
            pr_by_author[login] = []
        pr_by_author[login].append((days_ago, additions, deletions))
    print(f"  Found {len(prs)} merged PRs from {len(pr_by_author)} authors")

    # Score each contributor
    scored = {}
    for login, commit_days in contrib.items():
        # 1. Commit score with time decay (floor at 10%)
        commit_score = 0.0
        for d in commit_days:
            decay = max(0.1, 0.5 ** (d / 30))  # 30-day half-life, 10% floor
            commit_score += decay

        # 2. PR size factor — use the median PR size for this author
        author_prs = pr_by_author.get(login, [])
        if author_prs:
            sizes = [_pr_size_factor(a, dd) for a, dd in [(x[1], x[2]) for x in author_prs]]
            sizes.sort()
            median_size = sizes[len(sizes) // 2]
            # Scale: median_size / 2.0 normalizes around 1.0 for typical PRs
            size_multiplier = median_size / 2.0
        else:
            size_multiplier = 0.5  # no PR data → small default

        # 3. Recency bonus — based on most recent commit
        most_recent = min(commit_days) if commit_days else 365
        recency = _recency_bonus(most_recent)

        total = commit_score * size_multiplier + recency
        scored[login] = total

    # 排除自产自销账号
    EXCLUDE_LOGINS = {"misakanet-bot", "ikalus1988", "sheldonisspark-lab", "claude",
                      "actions-user", "cloudflare-workers-and-pages[bot]",
                      "dependabot[bot]", "pre-commit-ci[bot]"}
    scored = {k: v for k, v in scored.items() if k not in EXCLUDE_LOGINS}

    # Feature: lessons_contributed bonus — read source field from lesson frontmatter
    lessons_bonus = {}
    for lesson_file in sorted(LESSONS_DIR.rglob("*.md")):
        if lesson_file.name in ("index.md", "TEMPLATE.md", "README.md"):
            continue
        if "_archive" in lesson_file.parts:
            continue
        text = lesson_file.read_text(encoding="utf-8", errors="replace")
        m = re.match(r'^---\s*\n(\{.*?\})\s*\n---', text, re.DOTALL)
        if m:
            try:
                fm = json.loads(m.group(1))
                source = (fm.get("source") or "").lower().strip()
                if source and source not in ("unknown", "contribute-api", "bootstrap", ""):
                    lessons_bonus[source] = lessons_bonus.get(source, 0) + 1
            except json.JSONDecodeError:
                pass

    # Apply lessons_contributed bonus: each contributed lesson adds 0.5 points
    for login in scored:
        bonus = lessons_bonus.get(login, 0) * 0.5
        if bonus > 0:
            scored[login] += bonus
            print(f"  📚 {login}: +{bonus:.1f} from {lessons_bonus.get(login, 0)} lessons")

    # 排序
    sorted_contrib = sorted(scored.items(), key=lambda x: -x[1])
    return [{"login": login, "score": round(score, 2)} for login, score in sorted_contrib]


def load_previous_leaderboard():
    """读取上次的排行榜快照"""
    if LEADERBOARD_FILE.exists():
        try:
            return json.load(LEADERBOARD_FILE.open())
        except (json.JSONDecodeError, OSError):
            pass
    return None


def load_meta():
    """读取 leaderboard_meta.json，返回上次榜首"""
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_meta(meta: dict):
    """原子写入 leaderboard_meta.json"""
    LEADERBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = META_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(META_FILE)


def save_leaderboard(data):
    """保存排行榜快照"""
    LEADERBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, LEADERBOARD_FILE.open("w"), indent=2)
    print(f"  Leaderboard saved to {LEADERBOARD_FILE}")


def create_notification_issue(new_top, old_top, changed):
    """创建贡献榜变化的 Issue"""
    if old_top:
        title = f"🏆 Leaderboard Update: {new_top['login']} is now #1!"
        body_parts = [
            f"## Leaderboard Change Detected",
            "",
            f"| | Previous | Current |",
            f"|---|---|---|",
            f"| **#1** | {old_top['login']} ({old_top['score']}) | **{new_top['login']} ({new_top['score']})** |",
            f"| **Changed** | {len(changed)} spots changed |",
            "",
            "### Full Leaderboard",
            "",
        ]
    else:
        title = f"🏆 First Leaderboard: {new_top['login']} takes #1!"
        body_parts = [
            f"## First Leaderboard Snapshot",
            "",
            "### Full Leaderboard",
            "",
        ]

    # 截取 Top 20
    body_parts.append("| Rank | Contributor | Score |")
    body_parts.append("|------|------------|-------|")
    for rank, entry in enumerate(changed[:20], 1):
        body_parts.append(f"| {rank} | {entry['login']} | {entry['score']} |")

    body_parts.extend([
        "",
        "_Auto-generated by leaderboard-watcher. Updated on every merge to main._",
        f"_Timestamp: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}_",
    ])

    if DRY_RUN:
        print(f"\n[Dry-Run] Would create issue: {title}")
        return True

    result = gh_api("POST", f"repos/{REPO}/issues", {
        "title": title,
        "body": "\n".join(body_parts),
        "labels": ["leaderboard", "automated"],
    })
    if result and "number" in result:
        print(f"  Issue #{result['number']} created: {result['html_url']}")
        return True
    return False


def main():
    if not TOKEN:
        print("❌ GH_TOKEN not set")
        sys.exit(1)

    print("=" * 50)
    print(f"Leaderboard Watch — {REPO}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Dry-run: {DRY_RUN}")
    print("=" * 50)

    # 1. 计算当前排行榜
    print("\n📊 Computing leaderboard...")
    current = compute_leaderboard()
    if not current:
        print("❌ Failed to compute leaderboard")
        sys.exit(1)
    print(f"  Total contributors: {len(current)}")
    print(f"  #1: {current[0]['login']} ({current[0]['score']})")

    # 2. 读取上次快照
    previous = load_previous_leaderboard()
    meta = load_meta()
    if previous:
        print(f"  Previous #1: {previous[0]['login']} ({previous[0]['score']})")
    else:
        print("  No previous leaderboard found (first run)")

    # 3. 对比 — 同时检查贡献榜和 bench 榜（通过 meta）
    contrib_changed = previous is None or (
        previous[0]["login"] != current[0]["login"] and
        abs(previous[0]["score"] - current[0]["score"]) > 0.5
    )

    bench_top_login = meta.get("top_agent", "")
    bench_top_score = meta.get("top_score", 0)
    bench_top = {"login": bench_top_login, "score": bench_top_score} if bench_top_login else None

    # Also check if bench leaderboard #1 changed via gen_leaderboard.py output
    bench_leaderboard_file = REPO_ROOT / "data" / "bench_leaderboard.json"
    bench_leaderboard = None
    if bench_leaderboard_file.exists():
        try:
            bl = json.loads(bench_leaderboard_file.read_text(encoding="utf-8"))
            if bl.get("leaderboard"):
                top_entry = bl["leaderboard"][0]
                bench_top_login = top_entry["agent"]
                bench_top_score = top_entry["passed"]
                bench_top = {"login": bench_top_login, "score": bench_top_score}
                prev_bench_top = meta.get("top_agent", "")
                if prev_bench_top and prev_bench_top != bench_top_login:
                    print(f"\n🔔 Bench leaderboard #1 changed: {prev_bench_top} → {bench_top_login}")
                    bench_leaderboard = bl["leaderboard"]
        except (json.JSONDecodeError, OSError):
            pass

    if contrib_changed or bench_leaderboard:
        print(f"\n🔔 Leaderboard changed! Creating notification...")
        old_top = previous[0] if previous else None
        new_top = current[0]
        create_notification_issue(new_top, old_top, current)
        if bench_leaderboard:
            print(f"  Bench #1: {bench_top_login} ({bench_top_score} tasks)")
    else:
        print(f"\n✅ Leaderboard unchanged. No notification needed.")

    # 4. 保存新快照
    save_leaderboard(current)

    # 5. 更新 meta（记录当前榜首，供下次对比）
    if bench_top:
        meta["top_agent"] = bench_top["login"]
        meta["top_score"] = bench_top["score"]
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_meta(meta)
        print(f"  Meta saved to {META_FILE}")

    print("\nDone.")


if __name__ == "__main__":
    main()
