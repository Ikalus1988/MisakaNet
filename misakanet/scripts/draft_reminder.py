#!/usr/bin/env python3
"""
MisakaNet Lesson Draft Reminder (v2)
======================================
扫描本地草稿和仓库中 status=draft 的 lesson，超 48h 未审则推飞书提醒。

用法:
  python3 misakanet/scripts/draft_reminder.py

Cron: 0 9,14 * * * python3 /path/to/MisakaNet/misakanet/scripts/draft_reminder.py
       (每天 9:00 和 14:00 各跑一次)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent / ".." / ".."
LESSONS_DIR = PROJECT_ROOT / "lessons"
DRAFTS_DIR = Path.home() / ".hermes" / "lessons" / "drafts"
STALE_HOURS = 48


def _get_webhook_url() -> str:
    """从环境变量或 config.yaml 读取飞书 webhook URL"""
    url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if url:
        return url
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        import yaml
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            url = cfg.get("feishu", {}).get("webhook_url", "")
            if url and "${" not in url:
                return url
        except Exception:
            pass
    return ""


def _get_file_age_hours(path: Path) -> float:
    """文件最后修改距今的小时数"""
    now = datetime.now().timestamp()
    age = now - path.stat().st_mtime
    return age / 3600


def _get_lesson_age_from_git(filepath: Path) -> float | None:
    """通过 git log 获取 lesson 文件最后提交距今的小时数"""
    try:
        rel = filepath.relative_to(PROJECT_ROOT)
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", str(rel)],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode == 0 and result.stdout.strip():
            commit_ts = int(result.stdout.strip())
            return (datetime.now().timestamp() - commit_ts) / 3600
    except Exception:
        pass
    return None


def _scan_drafts() -> list[dict]:
    """扫描 ~/.hermes/lessons/drafts/ 中超 48h 的草稿"""
    stale = []
    if not DRAFTS_DIR.exists():
        return stale
    for f in sorted(DRAFTS_DIR.glob("*.md")):
        age = _get_file_age_hours(f)
        if age > STALE_HOURS:
            title = f.name.replace(".md", "").replace("_auto_", " | ")
            stale.append({
                "source": "drafts",
                "title": title,
                "age_h": round(age),
                "path": str(f),
            })
    return stale


def _scan_repo_drafts() -> list[dict]:
    """扫描 lessons/*.md 中 status: draft 且超 48h 未审的"""
    stale = []
    if not LESSONS_DIR.exists():
        return stale
    for f in sorted(LESSONS_DIR.glob("**/*.md")):
        if f.name == "index.md":
            continue
        content = f.read_text(encoding="utf-8")
        if "status: draft" not in content:
            continue
        # 提取 title
        title = ""
        for line in content.split("\n"):
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip('"').strip("'")
                break
        if not title:
            title = f.name.replace(".md", "")
        # 用 git log 判断年龄
        age = _get_lesson_age_from_git(f)
        if age is not None and age > STALE_HOURS:
            stale.append({
                "source": "repo",
                "title": title,
                "age_h": round(age),
                "path": str(f),
            })
    return stale


def _push_feishu(draft_items: list[dict], repo_items: list[dict]):
    """推送到飞书"""
    webhook = _get_webhook_url()
    if not webhook:
        print("[draft_reminder] 未配置飞书 webhook，跳过通知")
        return

    lines = ["📝 MisakaNet Lesson 草稿提醒"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if draft_items:
        lines.append(f"\n⏳ 本地草稿待审 ({len(draft_items)} 条):")
        for item in draft_items:
            lines.append(f"  • {item['title']} ({item['age_h']}h)")
        lines.append("  审核: queue_hook_stats.py promote <filename>")

    if repo_items:
        lines.append(f"\n📄 lessons/ 中 draft 待审 ({len(repo_items)} 条):")
        for item in repo_items:
            lines.append(f"  • {item['title']} ({item['age_h']}h)")
        lines.append("  审核: 编辑文件将 status: draft → status: active")
        lines.append("  或: queue_lesson.py promote <filename>")

    if not draft_items and not repo_items:
        lines.append("\n✅ 无待审草稿")

    lines.append(f"\n---\n巡检时间: {now}")

    text = "\n".join(lines)
    payload = {"msg_type": "text", "content": {"text": text}}

    import requests
    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"  ✅ Feishu 推送成功 ({len(draft_items) + len(repo_items)} 条提醒)")
        else:
            print(f"  ⚠ Feishu 推送返回 {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  ⚠ Feishu 推送失败: {e}")


def main():
    print(f"=== MisakaNet Draft Reminder ===")
    print(f"  草稿目录: {DRAFTS_DIR}")
    print(f"  lessons 目录: {LESSONS_DIR}")
    print(f"  超时阈值: {STALE_HOURS}h")

    draft_items = _scan_drafts()
    repo_items = _scan_repo_drafts()

    print(f"  本地草稿超 {STALE_HOURS}h: {len(draft_items)} 条")
    print(f"  lessons/ draft 超 {STALE_HOURS}h: {len(repo_items)} 条")

    if draft_items:
        for item in draft_items:
            print(f"    ⏳ {item['title']} ({item['age_h']}h)")

    if repo_items:
        for item in repo_items[:10]:  # 防止刷屏
            print(f"    📄 {item['title']} ({item['age_h']}h)")
        if len(repo_items) > 10:
            print(f"    ... 还有 {len(repo_items) - 10} 条")

    _push_feishu(draft_items, repo_items)
    print("=== done ===")


if __name__ == "__main__":
    main()
