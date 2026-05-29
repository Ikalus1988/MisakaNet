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
    """调用 GitHub API。"""
    import urllib.request
    token = _get_token()
    if not token:
        print("  ❌ 未找到 GitHub Token")
        print("  设置: export GITHUB_TOKEN=ghp_xxx")
        return None
    url = f"{API_BASE}/repos/{REPO}/{path}"
    headers = {**HEADERS, "Authorization": f"token {token}"}
    body = json.dumps(data).encode() if data else None
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ❌ API 错误 ({e.code}): {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
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


def main():
    parser = argparse.ArgumentParser(description="GitHub API 一键贡献 lesson")
    parser.add_argument("file", nargs="?", help="lesson 文件路径")
    parser.add_argument("-t", "--title", help="标题（配合 --content）")
    parser.add_argument("-d", "--domain", default="general", help="领域")
    parser.add_argument("content", nargs="?", help="内容（配合 -t -d）")
    args = parser.parse_args()

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
