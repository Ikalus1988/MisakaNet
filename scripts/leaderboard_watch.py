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


# Identities that are not independent contributors.
#
# `[bot]` is GitHub's own convention for an App (and the only shape that generalises): any App that
# ever commits here is caught by the suffix, without anybody maintaining a list. The explicit set
# below is *this repository's* automation — the git identities its workflows configure, which have no
# GitHub account at all, so no `type` field exists to consult for them.
SELF_IDENTITIES = {
    "misakanet-bot",         # scripts/adopt_pr.py DEFAULT_SIGNOFF_NAME; 7 workflows `git config user.name`
    "misakanet-sync-bot",    # .github/workflows/auto-sync-prs.yml
    "misakanet-agent",       # older tooling identity (no GitHub account)
    "misakanet agent",       #   "        (same, with a space)
    "github-actions",        # the *name* GitHub's own runner commits with, distinct from [bot]
    "actions-user",          # GitHub's legacy actions identity
    "ikalus1988",            # the maintainer: excluded so the board is about contributors
    "sheldonisspark-lab",    # maintainer's second account
    "claude",                # a coding agent used here
}


def board_moved(previous: list[dict], current: list[dict], threshold: float = 0.5) -> bool:
    """Whether the *visible* board changed: the ranking order, or any score by more than `threshold`.

    Deliberately not "did the top entry change". A board can be wrong in every other row — a bot in
    second place, a contributor dropped — while #1 is untouched, and with the old predicate that
    correction was computed and then thrown away (measured 2026-09-25).
    """
    if [r.get("login") for r in previous] != [r.get("login") for r in current]:
        return True
    for before, after in zip(previous, current):
        try:
            if abs(float(before.get("score", 0)) - float(after.get("score", 0))) > threshold:
                return True
        except (TypeError, ValueError):
            return True
    return False


def is_automation_login(login: str) -> bool:
    """True for GitHub Apps and for this repository's own automation identities.

    Not a judgement about whether a *person* is behind an account — GitHub cannot tell us that, and
    this project's own `agent_type` is self-declared and unverified. It answers the narrower, checkable
    question: is this identity the project's own machinery?
    """
    name = str(login or "").strip().lower()
    return name.endswith("[bot]") or name in SELF_IDENTITIES


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

    # 排除自产自销与自动化账号 —— 按**规则**而不是按一张要人记得更新的清单。
    #
    # 这张清单漏掉了 `github-actions[bot]`：仓库里最活跃的自动化身份，2026-09-25 实测它坐在公开
    # "贡献排行" 的**第 2 名**（7.54），而清单里却写着 dependabot / pre-commit-ci / cloudflare 三个
    # 更少露面的 bot。同一个漏洞还漏掉 `misakanet-sync-bot`（第 5 名）—— 那是
    # `.github/workflows/auto-sync-prs.yml` 里 `git config user.name` 设的身份，没有对应的 GitHub
    # 账号，所以它连用户页都是 404，却照样上榜；`misakanet agent` / `misakanet-agent` / `github-actions`
    # 同理（都是本仓工具写入的裸 git 身份）。
    #
    # 另外，榜上的"贡献者"来自提交作者：GraphQL 能给到 GitHub 用户时用 login，否则**退化成 git 里的
    # 裸名字**（见上面 `login = ... or author.get("name")`）。所以任何身份都能上榜，包括不存在的账号 ——
    # 这也是为什么规则必须按形状判（`[bot]`）而不是按名字枚举。
    scored = {k: v for k, v in scored.items() if not is_automation_login(k)}

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

    # 快照该不该写盘，与"要不要通知"是两个问题，曾经被合并成一个（2026-09-20 → 2026-09-25）。
    #
    # 2026-09-20 的修法是对的：main 曾经有 1,026 个提交（占全仓 25%）只为保存一份只有时间戳不同的
    # 快照，还撞坏了 npm 发布的记账步骤。但当时用的判据是**"榜首换人了没有"**，于是
    # `data/leaderboard.json` 除了榜首易主那一刻之外**永远不会更新**。今天实测：脚本算出 #1 是
    # zsxh1990 (79.08)，而被提交的那份写着 94.81 —— 脚本把这个 15.7 分的差距称为 "no material change"，
    # 所以那份文件既保留着四个自动化身份，又慢了五天，而且**靠它自己永远修不回来**。
    #
    # 正确的判据是"算出来的榜与被提交的榜是否一致"：一致 → 不写（保住 2026-09-20 的成果）；
    # 不一致 → 写。为了不让每天的时间衰减制造无意义的提交，这里按**可见变化**判定：名次顺序变了，
    # 或者任一位的分数移动超过 0.5（与上面的通知阈值同一个尺度）。
    snapshot_changed = previous is None or board_moved(previous, current)

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

    # 4. 保存新快照 —— **只在真的变了时写盘**（2026-09-20）
    #
    # 这里过去是无条件写盘，并且每次都盖上新的 `updated_at` 时间戳，于是**每次 push 都会产生一个
    # 只有时间戳不同的提交**：main 的历史里 1,026 个提交（占全仓 25%）只为保存这几个字段的状态，
    # 而工作流里明明有 `git diff --cached --quiet` 守卫——它永远不生效，因为 diff 从来不空。
    #
    # 代价不只是历史噪声：main 因此成为高频移动的目标，2026-09-20 npm 发布的 record 步骤就被这些提交
    # 撞成非快进（`! [rejected] HEAD -> main (fetch first)`），发布成功却没能记回仓库。
    #
    # 状态只在"榜首真的变了"时落盘，守卫随即生效：没有变化 → 没有提交。（快照仍是下次对比的基准，
    # 排行榜的实时视图本来就来自 Worker 的 `/api/insights/reputation-leaderboard`，不读这两个文件。）
    # 与通知分开：只要榜面动了就写盘（哪怕榜首没换），否则被提交的那份会一直错下去。
    material_change = bool(snapshot_changed or bench_leaderboard)
    if material_change:
        save_leaderboard(current)

        # 5. 更新 meta（记录当前榜首，供下次对比）
        if bench_top:
            meta["top_agent"] = bench_top["login"]
            meta["top_score"] = bench_top["score"]
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_meta(meta)
            print(f"  Meta saved to {META_FILE}")
    else:
        print("  no material change — snapshot not rewritten, so this run commits nothing")

    print("\nDone.")


if __name__ == "__main__":
    main()
