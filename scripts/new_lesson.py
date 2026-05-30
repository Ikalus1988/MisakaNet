#!/usr/bin/env python3
"""
交互式贡献模板 — 引导填写 Lesson 并自动生成标准 Markdown 文件。

用法:
  python3 scripts/new_lesson.py          ← 交互式向导
  python3 scripts/new_lesson.py --batch  ← 一行参数快速创建
"""
import argparse
import json
import os
import sys
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"

DOMAINS = sorted([
    "rag", "feishu", "development", "devops", "general",
    "python", "wsl", "git", "docker", "network",
    "security", "frontend", "testing", "ci-cd", "scripts",
])

WINDOWS_RESERVED_FILENAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def _slugify(title: str) -> str:
    """Return a cross-platform safe filename stem for a lesson title.

    Keep ASCII alphanumerics and CJK characters for readable lesson names,
    but collapse path separators, emoji, punctuation, control characters, and
    other filesystem-hostile input to hyphens. Always return a non-empty stem
    and avoid Windows device names such as ``CON`` and ``LPT1``.
    """
    normalized = unicodedata.normalize("NFKC", str(title)).casefold().strip()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", normalized)
    slug = re.sub(r"-+", "-", slug).strip("-")

    if not slug:
        slug = "lesson"
    if slug in WINDOWS_RESERVED_FILENAMES:
        slug = f"lesson-{slug}"

    slug = slug[:60].rstrip("-")
    return slug or "lesson"


def _input_or_default(prompt: str, default: str = "") -> str:
    if default:
        val = input(f"{prompt} [{default}]: ").strip()
    else:
        val = input(f"{prompt}: ").strip()
    return val if val else default


def _choose_domain() -> str:
    print("\n  可选领域:")
    for i, d in enumerate(DOMAINS, 1):
        print(f"    {i}. {d}")
    while True:
        choice = input("  选择编号或直接输入领域名: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(DOMAINS):
                return DOMAINS[idx]
        elif choice:
            return choice
        print("  无效选择，请重试")


def interactive():
    print("\n" + "=" * 50)
    print("  MisakaNet — 贡献新 Lesson")
    print("=" * 50)

    title = _input_or_default("问题/踩坑标题")
    if not title:
        print("  ❌ 标题不能为空")
        return False

    domain = _choose_domain()
    tags_raw = _input_or_default("标签（逗号分隔）")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    print("\n  --- 以下是模板引导，逐项填写 ---")
    problem = _input_or_default("  1. 遇到什么问题")
    root_cause = _input_or_default("  2. 根因是什么")
    fix = _input_or_default("  3. 怎么修复的")
    verify = _input_or_default("  4. 怎么验证修复结果")

    source = os.environ.get("MISAKANET_NODE_ID", "manual")
    now = datetime.now(timezone.utc)

    frontmatter = {
        "title": title,
        "domain": domain,
        "source": source,
        "status": "published",
        "tags": tags,
        "created": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    body = f"""---
{json.dumps(frontmatter, ensure_ascii=False)}
---

## 问题

{problem}

## 根因

{root_cause}

## 修复方案

{fix}

## 验证

{verify}

---

*自动生成于 {now.strftime('%Y-%m-%d %H:%M:%S')} UTC | 来源: {source}*
"""

    filename = f"{_slugify(title)}.md"
    filepath = LESSONS_DIR / filename

    print(f"\n  即将写入: {filepath}")
    print(f"  标题: {title}")
    print(f"  领域: {domain}")
    print(f"  标签: {tags}")
    confirm = input("  确认写入? (Y/n): ").strip().lower()
    if confirm == "n":
        print("  ❌ 已取消")
        return False

    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(body, encoding="utf-8")
    from misakanet.profile import increment_lesson
    increment_lesson()
    print(f"  ✅ lesson 已创建: {filepath}")
    print(f"\n  查看: cat {filepath}")
    print(f"  同步: python3 misakanet/scripts/queue_lesson.py --file {filepath}")
    return True


def batch(title: str, domain: str, content: str, tags: list[str] = None):
    """非交互式快速创建，适合 agent 调用。"""
    source = os.environ.get("MISAKANET_NODE_ID", "agent")
    now = datetime.now(timezone.utc)

    frontmatter = {
        "title": title,
        "domain": domain or "general",
        "source": source,
        "status": "published",
        "tags": tags or [],
        "created": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    body = f"""---
{json.dumps(frontmatter, ensure_ascii=False)}
---

{content}

---

*自动生成于 {now.strftime('%Y-%m-%d %H:%M:%S')} UTC | 来源: {source}*
"""

    filename = f"{_slugify(title)}.md"
    filepath = LESSONS_DIR / filename
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(body, encoding="utf-8")
    print(f"  ✅ {filepath}")
    return filepath


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="贡献模板 — 创建标准 Lesson")
    parser.add_argument("--batch", nargs=4, metavar=("title", "domain", "content", "tags"),
                        help="批量模式: 标题 领域 内容 标签(逗号分隔)")
    args = parser.parse_args()

    if args.batch:
        batch(args.batch[0], args.batch[1], args.batch[2],
              [t.strip() for t in args.batch[3].split(",") if t.strip()])
    else:
        interactive()
