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


def compute_leaderboard():
    """从 GitHub API 获取贡献数据，计算排行榜"""
    print("Fetching commit history via GraphQL...")
    contrib = {}
    cursor = None
    page = 0

    while page < 20:  # 最多 20 页 = 2000 commits
        page += 1
        q = GRAPHQL_QUERY
        if cursor:
            q = q.replace('$cursor: String', '$cursor: String', 1)
            q = q.replace('after: $cursor', f'after: "{cursor}"')

        # 直接用 hardcoded query 避免占位符问题
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
        """ % (REPO.split("/")[0], REPO.split("/")[1],
               f'after: "{cursor}"' if cursor else "")

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

            # 时间衰减权重：30天半衰期
            weight = max(0.1, 0.5 ** (days_ago / 30))
            contrib[login] = contrib.get(login, 0.0) + weight

        if not history["pageInfo"]["hasNextPage"]:
            break
        cursor = history["pageInfo"]["endCursor"]
        time.sleep(0.5)  # 限速保护

    # 排除自产自销账号
    EXCLUDE_LOGINS = {"misakanet-bot", "ikalus1988", "sheldonisspark-lab", "claude",
                      "actions-user", "cloudflare-workers-and-pages[bot]",
                      "dependabot[bot]", "pre-commit-ci[bot]"}
    contrib = {k: v for k, v in contrib.items() if k not in EXCLUDE_LOGINS}

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
    for login in contrib:
        bonus = lessons_bonus.get(login, 0) * 0.5
        if bonus > 0:
            contrib[login] += bonus
            print(f"  📚 {login}: +{bonus:.1f} from {lessons_bonus.get(login, 0)} lessons")

    # 排序
    sorted_contrib = sorted(contrib.items(), key=lambda x: -x[1])
    return [{"login": login, "score": round(score, 2)} for login, score in sorted_contrib]


def load_previous_leaderboard():
    """读取上次的排行榜快照"""
    if LEADERBOARD_FILE.exists():
        try:
            return json.load(LEADERBOARD_FILE.open())
        except (json.JSONDecodeError, OSError):
            pass
    return None


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
    if previous:
        print(f"  Previous #1: {previous[0]['login']} ({previous[0]['score']})")
    else:
        print("  No previous leaderboard found (first run)")

    # 3. 对比
    changed = previous is None or (
        previous[0]["login"] != current[0]["login"] and
        abs(previous[0]["score"] - current[0]["score"]) > 0.5
    )

    if changed:
        print(f"\n🔔 Leaderboard changed! Creating notification...")
        old_top = previous[0] if previous else None
        new_top = current[0]
        create_notification_issue(new_top, old_top, current)
    else:
        print(f"\n✅ Leaderboard unchanged. No notification needed.")

    # 4. 保存新快照
    save_leaderboard(current)
    print("\nDone.")


if __name__ == "__main__":
    main()
