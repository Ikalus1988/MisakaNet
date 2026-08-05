#!/usr/bin/env python3
"""
MisakaNet Queue Lesson (节点侧)
===============================
踩坑后写一条关键 Lesson 到共享仓库，其他节点启动时自动读取。

用法:
  # 方式 1: 从参数创建
  python3 scripts/queue_lesson.py \
    --title "FANUC R-2000iC 检索混淆修复" \
    --domain rag-retrieval \
    --tags fanuc,r-2000ic \
    "根因: 跨品牌型号字符串 \"2000\" 同时匹配 KUKA 和 FANUC..."

  # 方式 2: 简化版
  python3 scripts/queue_lesson.py \
    -t "标题" -d rag-retrieval "内容..."

  # 方式 3: 已编辑好的 md 文件 (clean_pipeline 输出、手动编辑等)
  python3 scripts/queue_lesson.py --file path/to/lesson.md
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# 自动更新 lessons.json（make sure scripts/ 在 sys.path 里）
_SCRIPTS_DIR = Path(__file__).resolve().parent
if _SCRIPTS_DIR.exists() and str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

REPO = "Ikalus1988/MisakaNet"
NODE_ID = os.environ.get("MISAKANET_NODE_ID", "hermes_wsl2")
REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = Path(os.environ.get("LESSONS_DIR", str(REPO_ROOT / "lessons")))


def _get_token():
    """Get GitHub token securely via git credential helper"""
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n",
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    # Fallback: read from file with proper handling
    try:
        cred_path = os.path.expanduser("~/.git-credentials")
        with open(cred_path, 'r') as f:
            creds = f.read().strip()
        return creds.split("://")[1].split("@")[0].split(":")[1]
    except Exception:
        return None


def _slugify(title):
    """标题 → 文件名: 英文+数字+连字符"""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    slug = slug.strip("-")
    # 保留中文+英文混合, 截断
    return slug[:60]


def _update_index(new_file, title, domain, tags, source):
    """更新 lessons/index.md 目录"""
    index_path = LESSONS_DIR / "index.md"
    os.makedirs(LESSONS_DIR, exist_ok=True)

    lines = []
    if index_path.exists():
        lines = index_path.read_text(encoding="utf-8").split("\n")

    # 找分割线后的条目区
    entry = f"- [{title}]({new_file.name}) | {domain} | {', '.join(tags)} | {source}"
    if entry not in lines:
        lines.append(entry)

    # 重构整个 index.md
    header = [
        "# MisakaNet Shared Lessons",
        "",
        f"> 最后更新: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC | 来源: {source}",
        "",
        "每条 lesson 包含踩坑记录、修复方法和验证方式，跨节点自动同步。",
        "",
        "## 目录",
        "",
        "| Lesson | Domain | Tags | Source |",
        "|--------|--------|------|--------|",
    ]
    body_lines = []
    for l in lines:
        if l.startswith("- ["):
            body_lines.append(l)

    # 排序：按标题字母序
    body_lines = sorted(body_lines)

    content = "\n".join(header + body_lines + [""])
    index_path.write_text(content, encoding="utf-8")
    print(f"  index: {len(body_lines)} lessons")

def _print_suggested_git(filename, title):
    rel = f"lessons/contrib/{filename}"
    print("\n# Suggested next steps (not executed):")
    print(f"git add {shlex.quote(rel)}")
    print(f"git commit --signoff -m {shlex.quote(f'lessons: {title}')}")
    print("git push origin main")


def _render_lesson(title, domain, tags, content, source=NODE_ID, status="published"):
    """Build lesson slug, filename and markdown body without writing files."""
    slug = _slugify(title)
    filename = f"{slug}.md"

    now = datetime.now(timezone.utc)
    frontmatter = {
        "title": title,
        "domain": domain,
        "source": source,
        "status": status,
        "tags": tags,
        "created": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    body = f"---\n{json.dumps(frontmatter, ensure_ascii=False)}\n---\n\n{content}\n"
    return slug, filename, body


def write_lesson(title, domain, tags, content, source=NODE_ID, status="published"):
    """写一条 lesson 文件 + 更新 index + git push"""

    slug = _slugify(title)
    filename = f"{slug}.md"
    filepath = LESSONS_DIR / filename

    now = datetime.now(timezone.utc)

    # 如果文件已存在，追加内容（同一主题的更新）
    mode = "更新" if filepath.exists() else "新建"
    existing_content = filepath.read_text(encoding="utf-8") if filepath.exists() else ""

    frontmatter = {
        "title": title,
        "domain": domain,
        "source": source,
        "status": status,
        "tags": tags,
        "created": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    body = f"---\n {json.dumps(frontmatter, ensure_ascii=False)}\n ---\n\n{content}\n"

    if existing_content:
        body = existing_content.rstrip() + f"\n\n---\n\n### 更新 ({now.strftime('%Y-%m-%d')})\n\n{content}\n"

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(body, encoding="utf-8")

    _update_index(filepath, title, domain, tags, source)

    # git commit + push (cwd= 参数避免 os.chdir 竞态)
    token = _get_token()
    repo_root = REPO_ROOT

    subprocess.run(["git", "add", str(filepath), str(LESSONS_DIR / "index.md")],
                   capture_output=True, cwd=str(repo_root))
    subprocess.run(["git", "commit", "-m", f"lessons: {title}"],
                   capture_output=True, timeout=10, cwd=str(repo_root))

    push = subprocess.run(["git", "push", "origin", "main"],
                          capture_output=True, text=True, timeout=20,
                          cwd=str(repo_root))

    if push.returncode == 0:
        # 更新 lessons.json 索引
        try:
            from update_lessons_json import main as rebuild_index
            rebuild_index()
            print(f"   📋 lessons.json 已更新")
        except Exception:
            pass
        print(f"✅ {mode} lesson: {filename}")
        print(f"   title: {title}")
        print(f"   domain: {domain}")
        print(f"   tags: {tags}")
        print(f"   → 已同步到 GitHub")
        return True
    else:
        # git push 失败 → 写入本地暂存队列，网络恢复后由 Hub 下发
        import json as _json
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pending_dir = REPO_ROOT / ".feedback" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        pending_file = pending_dir / f"lesson_{ts}_{filename}"
        pending_file.write_text(body, encoding="utf-8")
        meta_file = pending_dir / f"lesson_{ts}_{filename}.meta.json"
        meta_file.write_text(_json.dumps({
            "title": title, "domain": domain, "tags": tags,
            "source": source, "queued_at": ts, "filename": str(filepath),
        }, ensure_ascii=False), encoding="utf-8")
        print(f"❌ git push 失败: {push.stderr.strip()}")
        print(f"   → lesson 暂存本地: {pending_file}")
        print(f"   → 网络恢复后，Hub 会自动同步此队列")
        return False


def write_lesson_from_file(filepath: str) -> bool:
    """从已编辑好的 md 文件导入 lesson + git push

    支持两种 frontmatter 格式:
      - JSON (queue_lesson.py 生成的)
      - YAML (clean_pipeline.py 生成的)
    """
    src = Path(filepath)
    if not src.exists():
        print(f"[error] 文件不存在: {filepath}", file=sys.stderr)
        return False

    content = src.read_text(encoding="utf-8")
    if not content.startswith("---"):
        print(f"[error] 缺少 frontmatter: {filepath}", file=sys.stderr)
        return False

    parts = content.split("---", 2)
    if len(parts) < 3:
        print(f"[error] frontmatter 格式错误: {filepath}", file=sys.stderr)
        return False

    # 尝试 JSON 解析 (queue_lesson.py 格式)，回退到 YAML 行解析
    fm_raw = parts[1].strip()
    try:
        fm = json.loads(fm_raw)
    except (json.JSONDecodeError, ValueError):
        fm = _parse_frontmatter_yaml(fm_raw)

    title = fm.get("title", src.stem)
    domain = fm.get("domain", "general")
    source = fm.get("source", NODE_ID)
    tags_raw = fm.get("tags", [])
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.strip("[]").split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    else:
        tags = []

    # 生成目标路径
    slug = _slugify(title)
    filename = f"{slug}.md"
    dest = LESSONS_DIR / filename

    # 覆盖写入（保留原内容，只更新 frontmatter 中的 source）
    fm["source"] = source
    fm["status"] = "published"  # file import 默认 published，不继承草稿状态
    fm["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    body = f"---\n{json.dumps(fm, ensure_ascii=False)}\n---\n\n{parts[2].strip()}\n"

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")

    _update_index(dest, title, domain, tags, source)

    # git commit + push (cwd= 参数避免 os.chdir 竞态)
    token = _get_token()
    repo_root = REPO_ROOT

    subprocess.run(["git", "add", str(dest), str(LESSONS_DIR / "index.md")],
                   capture_output=True, cwd=str(repo_root))
    subprocess.run(["git", "commit", "-m", f"lessons: {title} (--file import)"],
                   capture_output=True, timeout=10, cwd=str(repo_root))

    push = subprocess.run(["git", "push", "origin", "main"],
                          capture_output=True, text=True, timeout=20,
                          cwd=str(repo_root))

    if push.returncode == 0:
        print(f"✅ 导入 lesson: {filename} (from {src.name})")
        print(f"   title: {title}")
        print(f"   domain: {domain}")
        print(f"   → 已同步到 GitHub")
        return True
    else:
        print(f"❌ git push 失败: {push.stderr.strip()}")
        return False


def _parse_frontmatter_yaml(raw: str) -> dict:
    """简易 YAML frontmatter 解析 (兼容 clean_pipeline 格式)"""
    fm = {}
    for line in raw.strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'").strip("[]")
            if val:
                fm[key] = val
    return fm


def main():
    parser = argparse.ArgumentParser(description="写一条跨节点共享的 Lesson")
    parser.add_argument("-t", "--title", help="Lesson 标题")
    parser.add_argument("-d", "--domain", default="general", help="Domain 分类")
    parser.add_argument("--tags", default="", help="逗号分隔的标签")
    parser.add_argument("--status", default="published",
                        choices=["published", "draft", "deprecated"],
                        help="lesson 状态，默认 published")
    parser.add_argument("--file", help="已编辑好的 md 文件路径 (跳过 --title/正文参数)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview markdown; do not write files or run git")
    parser.add_argument("--suggest-git", action="store_true",
                        help="With --dry-run, print suggested git commands only")
    parser.add_argument("content", nargs="?", help="Lesson 内容（或通过 stdin）")
    args = parser.parse_args()

    if args.suggest_git and not args.dry_run:
        parser.error("--suggest-git requires --dry-run")

    # --file 模式: 直接导入
    if args.file:
        if args.dry_run:
            src = Path(args.file)
            if not src.exists():
                print(f"[error] file not found: {args.file}", file=sys.stderr)
                sys.exit(1)
            content = src.read_text(encoding="utf-8")
            print(content)
            if args.suggest_git:
                parts = content.split("---", 2)
                fm_raw = parts[1].strip() if len(parts) > 1 else ""
                try:
                    fm = json.loads(fm_raw)
                except Exception:
                    fm = _parse_frontmatter_yaml(fm_raw)
                title = fm.get("title", src.stem)
                slug = _slugify(title)
                filename = f"{slug}.md"
                print("\n# Suggested commands to apply this preview:\n")
                print(f"git add lessons/contrib/{filename}")
                print(f"git commit --signoff -m 'lessons: {title}'")
                print("git push origin main")
            sys.exit(0)
        ok = write_lesson_from_file(args.file)
        print("=== done ===" if ok else "=== failed ===")
        sys.exit(0 if ok else 1)

    # 原有模式: --title + content
    if not args.title:
        print("[error] 需要 --title 或 --file", file=sys.stderr)
        sys.exit(1)

    content = args.content
    if not content and not sys.stdin.isatty():
        content = sys.stdin.read().strip()

    if not content:
        print("[error] 需要提供 content（参数或 stdin）", file=sys.stderr)
        sys.exit(1)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    if args.dry_run:
        slug, filename, body = _render_lesson(args.title, args.domain, tags, content, source=NODE_ID, status=args.status)
        print(body)
        if args.suggest_git:
            _print_suggested_git(filename, args.title)
        sys.exit(0)

    write_lesson(args.title, args.domain, tags, content, status=args.status)
    print("=== done ===")


if __name__ == "__main__":
    main()
