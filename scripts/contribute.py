#!/usr/bin/env python3
"""
GitHub API 一键贡献 — 无需 fork / PAT / git push，直接通过 API 提交 PR。

用法:
  python3 scripts/contribute.py path/to/lesson.md
  python3 scripts/contribute.py -t "标题" -d domain "内容..."

前提:
  - 需要 GitHub Token（环境变量 GITHUB_TOKEN 或 ~/.git-credentials）
  - 仅创建 PR，不会直接写入 main 分支
"""
import argparse
import json
import os
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = "Ikalus1988/MisakaNet"
LESSONS_DIR = Path(__file__).resolve().parent.parent / "lessons"

API_BASE = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "MisakaNet-Contribute/1.0",
}


def _get_token() -> str | None:
    """获取 GitHub token：环境变量 → git credential → 文件。"""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n",
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    try:
        cred_path = os.path.expanduser("~/.git-credentials")
        with open(cred_path) as f:
            creds = f.read().strip()
        return creds.split("://")[1].split("@")[0].split(":")[1]
    except Exception:
        return None


def _api(path: str, data: dict = None, method: str = "POST") -> dict | None:
    """调用 GitHub API，支持指数退避的自动重试（最多 3 次重试）。"""
    import urllib.request
    import urllib.error
    import time
    token = _get_token()
    if not token:
        print("  ❌ 未找到 GitHub Token")
        print("  设置: export GITHUB_TOKEN=ghp_xxx")
        return None
    url = f"{API_BASE}/repos/{REPO}/{path}"
    headers = {**HEADERS, "Authorization": f"token {token}"}
    body = json.dumps(data).encode() if data else None
    
    max_retries = 3
    base_backoff = 1.0
    
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            # 只有 5xx 状态码或 429 (Too Many Requests) 应该被重试
            if e.code >= 500 or e.code == 429:
                if attempt < max_retries:
                    sleep_time = base_backoff * (2 ** attempt)
                    print(f"  ⚠️ API 临时错误 ({e.code})，正在进行第 {attempt + 1} 次重试，将在 {sleep_time} 秒后重试...")
                    time.sleep(sleep_time)
                    continue
            print(f"  ❌ API 错误 ({e.code}): {e.read().decode()[:200]}")
            return None
        except Exception as e:
            if attempt < max_retries:
                sleep_time = base_backoff * (2 ** attempt)
                print(f"  ⚠️ 网络请求异常 ({e})，正在进行第 {attempt + 1} 次重试，将在 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
                continue
            print(f"  ❌ 请求失败 (已达最大重试次数): {e}")
            return None


def _slugify(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    return slug.strip("-")[:60]


def _read_lesson(path: str) -> dict | None:
    """读取 lesson 文件，解析 frontmatter 和内容。"""
    fp = Path(path)
    if not fp.exists():
        print(f"  ❌ 文件不存在: {path}")
        return None
    content = fp.read_text(encoding="utf-8")
    # Parse JSON frontmatter
    m = re.match(r'^---\s*\n?(\{.*?\})\n?---', content, re.DOTALL)
    if m:
        try:
            meta = json.loads(m.group(1))
        except json.JSONDecodeError:
            meta = {}
    else:
        # Try YAML frontmatter
        m2 = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        meta = {}
        if m2:
            for line in m2.group(1).split("\n"):
                if ":" not in line:
                    continue
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip().strip('"').strip("'")
    # Body after frontmatter
    body_start = 0
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body_start = len(parts[0]) + len(parts[1]) + 6
    body = content[body_start:].strip()
    return {
        "meta": meta,
        "title": meta.get("title", fp.stem),
        "domain": meta.get("domain", ""),
        "tags": meta.get("tags", []),
        "body": body,
        "content": content,
        "filename": fp.name,
    }


def contribute(filepath: str):
    """提交一个 lesson 文件为 GitHub PR。"""
    lesson = _read_lesson(filepath)
    if not lesson:
        return False

    title = lesson["title"]
    filename = f"{_slugify(title)}.md"
    branch = f"contribute/{_slugify(title)[:40]}"

    # 1. 获取默认分支最新 SHA
    ref_info = _api(f"git/ref/heads/main", method="GET")
    if not ref_info:
        return False
    base_sha = ref_info["object"]["sha"]

    # 2. 创建新分支
    branch_data = {"ref": f"refs/heads/{branch}", "sha": base_sha}
    if not _api("git/refs", data=branch_data):
        return False
    print(f"  ✅ 分支创建: {branch}")

    # 3. 创建 blob（lesson 文件内容）
    blob = _api("git/blobs", data={"content": lesson["content"], "encoding": "utf-8"})
    if not blob:
        return False
    blob_sha = blob["sha"]

    # 4. 创建 tree
    tree = _api("git/trees", data={
        "base_tree": base_sha,
        "tree": [{
            "path": f"lessons/{filename}",
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha,
        }],
    })
    if not tree:
        return False
    tree_sha = tree["sha"]

    # 5. 创建 commit
    commit_msg = f"lessons: {title}\n\nContributed via API"
    commit = _api("git/commits", data={
        "message": commit_msg,
        "tree": tree_sha,
        "parents": [base_sha],
    })
    if not commit:
        return False
    commit_sha = commit["sha"]

    # 6. 更新分支引用
    _api(f"git/refs/heads/{branch}", data={"sha": commit_sha}, method="PATCH")

    # 7. 创建 PR
    domain_tag = f"[{lesson['domain']}]" if lesson["domain"] else ""
    pr_data = {
        "title": f"{domain_tag} {title}".strip(),
        "head": branch,
        "base": "main",
        "body": f"## 内容\n\n{lesson['body'][:500]}\n\n---\n*由 MisakaNet 贡献脚本自动创建*",
    }
    pr = _api("pulls", data=pr_data)
    if not pr:
        return False

    print(f"  ✅ PR 已创建: {pr['html_url']}")
    print(f"  标题: {pr['title']}")
    print(f"  分支: {branch}")
    return True


def _wizard():
    """交互式贡献向导 — 引导用户逐步填写 lesson 内容"""
    print("🎓 Welcome to Lesson Contribution Wizard!")
    print("Answer the questions below to create a new lesson.")
    print()

    # Step 1: Problem
    print("1. What's the problem you solved?")
    print("   (Describe the symptom, be specific)")
    problem = input("   > ").strip()
    while not problem:
        problem = input("   > ").strip()

    # Step 2: Domain
    known_domains = ["rag", "devops", "fanuc", "network", "feishu", "tts", "mcp", "agent-network", "marketing", "audio", "docker"]
    print(f"\n2. What domain is this? ({', '.join(known_domains)})")
    domain = input("   > ").strip().lower()
    if domain not in known_domains:
        print(f"   ⚠️  Unknown domain '{domain}', using it anyway.")

    # Step 3: Common problem?
    print("\n3. Is this a common problem? (affects multiple users/agents?) (y/n)")
    is_common = input("   > ").strip().lower().startswith("y")

    # Step 4: Root cause
    print("\n4. What's the root cause? (technical detail)")
    root_cause = input("   > ").strip()
    while not root_cause:
        root_cause = input("   > ").strip()

    # Step 5: Solution
    print("\n5. How to fix it? (describe step by step)")
    solution = input("   > ").strip()
    while not solution:
        solution = input("   > ").strip()

    # Step 6: Verification
    print("\n6. How to verify the fix works? (command or test)")
    verify = input("   > ").strip()
    while not verify:
        verify = input("   > ").strip()

    # Step 7: Environment
    print("\n7. What environment? (e.g., WSL2, Docker, Ubuntu 22.04, leave blank if generic)")
    env = input("   > ").strip()

    # Generate title from problem
    title = problem[:100]
    slug = _slugify(title)

    # Build tags
    tags = [domain]
    if is_common:
        tags.append("common")
    if env:
        tags.append(f"platform:{env.lower().replace(' ', '-')}")

    # Build content
    lines = [
        f"## Problem",
        "",
        problem,
        "",
        f"## Root Cause",
        "",
        root_cause,
        "",
        f"## Solution",
        "",
        solution,
        "",
        f"## Verification",
        "",
        verify,
        "",
    ]
    if env:
        lines.insert(0, f"**Environment:** {env}")
        lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("<!-- Add caveats, edge cases, related lessons here -->")
    lines.append("")

    content = "\n".join(lines)

    # Preview
    print()
    print("=" * 50)
    print("📝 Lesson Preview")
    print("=" * 50)
    print(f"Title: {title}")
    print(f"Domain: {domain}")
    print(f"Tags: {', '.join(tags)}")
    print(f"---")
    print(content)
    print("=" * 50)

    # Confirm
    print("\nReady to submit? (y/n)")
    confirm = input("   > ").strip().lower().startswith("y")
    if not confirm:
        print("Cancelled.")
        return False

    # Write temp file and submit
    tmp = LESSONS_DIR / f"__tmp_{slug}.md"
    body = f"""---
{{"title": "{title}", "domain": "{domain}", "tags": {json.dumps(tags)}, "status": "published", "created": "{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}", "updated": "{datetime.now(timezone.utc).strftime('%Y-%m-%d')}", "source": "contributor"}}
---

{content}
"""
    tmp.write_text(body, encoding="utf-8")
    try:
        ok = contribute(str(tmp))
        if ok:
            print(f"✅ Lesson submitted! Title: {title}")
            print(f"   Temp file: {tmp}")
            print(f"   It will be cleaned up after submission.")
        return ok
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="GitHub API 一键贡献 lesson")
    parser.add_argument("file", nargs="?", help="lesson 文件路径")
    parser.add_argument("-t", "--title", help="标题（配合 --content）")
    parser.add_argument("-d", "--domain", default="general", help="领域")
    parser.add_argument("content", nargs="?", help="内容（配合 -t -d）")
    parser.add_argument("--wizard", action="store_true", help="交互式贡献向导")
    args = parser.parse_args()

    if args.wizard:
        return _wizard() or 0
    if args.file:
        contribute(args.file)
    elif args.title and args.content:
        # 先写临时文件，再提交
        slug = _slugify(args.title)
        tmp = LESSONS_DIR / f"__tmp_{slug}.md"
        body = f"""---
{{"title": "{args.title}", "domain": "{args.domain}", "tags": [], "status": "published", "created": "{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}", "source": "contribute-api"}}
---

{args.content}
"""
        tmp.write_text(body, encoding="utf-8")
        ok = contribute(str(tmp))
        tmp.unlink(missing_ok=True)
        return ok
    else:
        parser.print_help()
        return False


if __name__ == "__main__":
    main()
