#!/usr/bin/env python3
"""从 lessons/ 实时统计，自动生成 STATUS.md。"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
REFERENCES_DIR = REPO / "reference"
OUTPUT = REPO / "STATUS.md"


def count_lessons():
    """统计 lessons 数量和各领域分布。"""
    lessons = []
    domains = {}
    for f in sorted(LESSONS_DIR.glob("**/*.md")):
        if f.name == "index.md" or f.name.startswith("."):
            continue
        lessons.append(f)
        content = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'"domain":\s*"([^"]+)"', content)
        if not m:
            m = re.search(r'^domain:\s*["\']?([^\n"\']+)', content, re.MULTILINE)
        d = m.group(1).strip() if m else "uncategorized"
        domains[d] = domains.get(d, 0) + 1

    return len(lessons), domains


def count_references():
    return len(list(REFERENCES_DIR.glob("**/*.md")))


def get_git_stats():
    """获取 git 提交统计。"""
    try:
        r = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(REPO),
        )
        commits = r.stdout.strip()
    except Exception:
        commits = "?"
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "--since=30.days", "--format=%H"],
            capture_output=True, text=True, timeout=5, cwd=str(REPO),
        )
        recent = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
    except Exception:
        recent = 0
    return commits, recent


def generate():
    lesson_count, domains = count_lessons()
    ref_count = count_references()
    git_commits, recent_commits = get_git_stats()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    top_domains = sorted(domains.items(), key=lambda x: -x[1])[:8]

    content = f"""# 项目状态

> 自动更新于 {now} | 由 scripts/update_status.py 生成

## 概览

| 指标 | 数值 |
|------|------|
| 📚 Lessons | {lesson_count} 篇 |
| 📖 References | {ref_count} 篇 |
| 🏛️ 领域覆盖 | {len(domains)} 个 |
| ✅ Git 提交 | {git_commits} 次 |
| 📈 近 30 天活跃度 | {recent_commits} 次提交 |

## 领域分布

| 领域 | 数量 |
|------|------|
"""
    for d, c in top_domains:
        bar = "█" * c + "░" * max(0, 20 - c) if c <= 20 else "█" * 20 + f" +{c - 20}"
        content += f"| {d:<20} | {bar} {c} |\n"

    content += f"""
## 节点就绪

| 节点 | 类型 | 状态 |
|------|------|------|
| Hermes (WSL) | Hub + Node | ✅ |
| cc-haha | Node | ✅ |
| OpenClaw | Node | ⏳ 待确认 |

## 活跃功能

| 功能 | 状态 |
|------|------|
| BM25 语义搜索 | ✅ 零依赖 |
| 搜索建议 `--suggest` | ✅ ≥2字符弹出 |
| 内容预览 + 高亮 + 分数条 | ✅ 彩色终端输出 |
| Lessons 共享 (git push) | ✅ |
| GitHub API 一键贡献 | ✅ scripts/contribute.py |
| 交互式安装向导 | ✅ scripts/setup.py |
| 贡献模板 | ✅ scripts/new_lesson.py |
| 质量评分 | ✅ scripts/score_lessons.py |
| 通知通道 (Discord/Slack/Email) | ✅ hub/sync/notifier.py |
| Hub 仲裁 | ✅ |
| Obsidian 集成 | ✅ |

## 快速开始

```bash
# 搜索
python3 search_knowledge.py "关键词"

# 搜索建议
python3 search_knowledge.py "pip" --suggest

# 贡献新 lesson
python3 scripts/new_lesson.py

# 通过 API 一键贡献 (需 GITHUB_TOKEN)
python3 scripts/contribute.py path/to/lesson.md

# 环境检查
python3 scripts/setup.py --check

# 质量评分
python3 scripts/score_lessons.py
```
"""
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"✅ STATUS.md 已更新 ({lesson_count} lessons, {len(domains)} domains)")


if __name__ == "__main__":
    generate()
