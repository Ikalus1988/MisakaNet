#!/usr/bin/env python3
"""
MisakaNet Hook Stats Logger (节点侧)
=====================================
cc-haha hook 触发时调用此脚本，记录一条原始触发事件。

用法:
  # 记录一条 hook 触发
  python3 misakanet/scripts/queue_hook_stats.py trigger \
    --node cc_haha --category network --hit lesson-filename.md

  # 手动汇总并推送
  python3 misakanet/scripts/queue_hook_stats.py flush --node cc_haha

  # 查看今日日志
  python3 misakanet/scripts/queue_hook_stats.py status
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

NODE_ID = os.environ.get("MISAKANET_NODE_ID", "cc_haha")
REPO_ROOT = Path(__file__).parent / ".." / ".."
HOOK_STATS_DIR = REPO_ROOT / ".hook_stats"
LOCAL_LOG_DIR = Path.home() / ".hermes" / "hook_stats"
LESSONS_DIR = Path(os.environ.get("LESSONS_DIR", REPO_ROOT / "lessons"))

CATEGORIES = ["network", "pip", "permission", "disk", "package_conflict", "model_output"]

# 模板检测：小于 1KB 且不含 "## 修复" 章节的 lesson 视为空模板
TEMPLATE_SIZE_THRESHOLD = 1024


def _is_template_lesson(filepath: Path) -> bool:
    """判断 lesson 文件是否为空模板（小尺寸 + 无修复节）"""
    if not filepath.exists() or filepath.name == "index.md":
        return False
    if filepath.stat().st_size > TEMPLATE_SIZE_THRESHOLD:
        return False
    content = filepath.read_text(encoding="utf-8")
    return "## 修复" not in content and "## 验证" not in content


def _fill_template(filepath: Path, category: str, node: str, error_msg: str):
    """向模板 lesson 追加一条真实触发记录，将其转变为'待修复'状态"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"""\n\n---\n\n### 触发记录\n\n- **首次触发**: {now}\n- **节点**: {node}\n- **分类**: {category}\n- **错误**: {error_msg}\n- **状态**: ⏳ 待修复\n"""

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"  📝 已填充模板: {filepath.name} (append trigger record)")
    return True


def _git_commit_template(filepath: Path, node: str, category: str):
    """将模板填充变更提交到仓库（数据无变化时跳过）"""
    try:
        os.chdir(str(REPO_ROOT))
        subprocess.run(["git", "add", str(filepath)], capture_output=True, timeout=10)
        # 检查是否有实际变更
        has_changes = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", str(filepath)],
            capture_output=True
        ).returncode == 1
        if not has_changes:
            print(f"  - {filepath.name} 无变化，跳过 commit")
            return
        subprocess.run(
            ["git", "commit", "-m", f"lessons: auto-fill {filepath.name} from {node}/{category} trigger"],
            capture_output=True, timeout=10,
        )
        subprocess.run(["git", "push", "origin", "main"],
                       capture_output=True, timeout=20)
        print(f"  → 已推送到仓库")
    except Exception as e:
        print(f"  ⚠ git push 失败: {e}")


def _generate_draft(category: str, node: str, error_msg: str):
    """hook 未命中 lesson 时生成待审草稿"""
    drafts_dir = Path.home() / ".hermes" / "lessons" / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    filename = f"{category}_auto_{now.strftime('%Y%m%d_%H%M%S')}.md"
    filepath = drafts_dir / filename

    content = f"""---
title: "[草稿] {category} 错误"
domain: {category}
source: {node}
status: draft
created: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}
---

## 问题

自动捕获于 {now.strftime('%Y-%m-%d %H:%M')}，节点 {node}。

**错误信息：**
```
{error_msg}
```

## 修复

（待填写 — 请补充修复步骤）

## 验证

（待填写 — 请补充验证方式）
"""
    filepath.write_text(content, encoding="utf-8")
    print(f"  📝 草稿已生成: {filepath}")
    print(f"     审: queue_hook_stats.py promote {filename}")
    print(f"     删: queue_hook_stats.py reject {filename}")


def cmd_list_drafts():
    """列出所有待审草稿"""
    drafts_dir = Path.home() / ".hermes" / "lessons" / "drafts"
    if not drafts_dir.exists():
        print("  无草稿")
        return

    now = datetime.now()
    files = sorted(drafts_dir.glob("*.md"))
    if not files:
        print("  无草稿")
        return

    print(f"  草稿 ({len(files)} 条):")
    for f in files:
        age_h = int((now - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() / 3600)
        title = f.name.replace("_auto_", " ").replace(".md", "")
        print(f"    [{age_h:3}h] {title}  ({f.name})")


def cmd_promote(draft_name: str):
    """将草稿提升为正式 lesson"""
    drafts_dir = Path.home() / ".hermes" / "lessons" / "drafts"
    draft_path = drafts_dir / draft_name
    if not draft_path.exists():
        print(f"[error] 草稿不存在: {draft_name}", file=sys.stderr)
        sys.exit(1)

    content = draft_path.read_text(encoding="utf-8")
    # 去掉 status: draft
    content = content.replace("status: draft", "status: published")
    content = content.replace("[草稿] ", "")

    lesson_path = LESSONS_DIR / draft_name
    lesson_path.write_text(content, encoding="utf-8")
    draft_path.unlink()

    # 提交到仓库
    _git_commit_template(lesson_path, "reviewer", "promoted")
    print(f"  ✅ 已发布: {lesson_path}")


def cmd_reject(draft_name: str):
    """删除草稿"""
    drafts_dir = Path.home() / ".hermes" / "lessons" / "drafts"
    draft_path = drafts_dir / draft_name
    if not draft_path.exists():
        print(f"[error] 草稿不存在: {draft_name}", file=sys.stderr)
        sys.exit(1)
    draft_path.unlink()
    print(f"  🗑 已删除: {draft_name}")


def _get_token():
    try:
        creds = open(os.path.expanduser("~/.git-credentials")).read().strip()
        return creds.split("://")[1].split("@")[0].split(":")[1]
    except Exception:
        return None


def cmd_trigger(node, category, hit=None, error=None):
    """记录一条原始触发事件到本地日志，并自动填充模板或生成草稿"""
    if category not in CATEGORIES:
        print(f"[error] category 必须是 {CATEGORIES} 之一", file=sys.stderr)
        sys.exit(1)

    LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = LOCAL_LOG_DIR / f"raw_{date_str}.jsonl"

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "node": node,
        "category": category,
        "hit": hit or "",
        "error": error or "",
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    hit_status = f"→ {hit}" if hit else "(未命中)"
    print(f"  ✓ 记录: {node}/{category} {hit_status}")

    if hit:
        lesson_path = LESSONS_DIR / hit
        if lesson_path.exists():
            if _is_template_lesson(lesson_path):
                _fill_template(lesson_path, category, node, error or "(错误信息未记录)")
                _git_commit_template(lesson_path, node, category)
        else:
            # hit 指向不存在的文件（如 hook 传的 "file" 等弱关键词）→ 降级为草稿
            print(f"  ↪ hit '{hit}' 不是有效 lesson，降级为草稿")
            _generate_draft(category, node, error or "(未记录)")
    else:
        # 未命中任何 lesson → 生成草稿
        _generate_draft(category, node, error or "(未记录)")


def cmd_flush(node):
    """汇总本地日志 → 写入仓库 .hook_stats/{node}.json + git push"""
    LOCAL_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 读取所有原始日志
    triggers = {c: 0 for c in CATEGORIES}
    hits = {c: 0 for c in CATEGORIES}
    total = 0

    for f in sorted(LOCAL_LOG_DIR.glob("raw_*.jsonl")):
        for line in f.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            try:
                r = json.loads(line)
                if r.get("node") != node:
                    continue
                cat = r.get("category", "")
                if cat in CATEGORIES:
                    triggers[cat] += 1
                    total += 1
                    if r.get("hit"):
                        hits[cat] += 1
            except json.JSONDecodeError:
                continue

    now = datetime.now(timezone.utc)

    summary = {
        "node": node,
        "updated_at": now.isoformat(),
        "total_triggers": total,
        "triggers": triggers,
        "hits": hits,
    }

    # 写入仓库
    HOOK_STATS_DIR.mkdir(parents=True, exist_ok=True)
    stats_path = HOOK_STATS_DIR / f"{node}.json"
    stats_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # git push（只有数据变化时才 commit，防止 git 日志刷屏）
    os.chdir(str(REPO_ROOT))
    subprocess.run(["git", "add", str(stats_path)], capture_output=True)
    has_changes = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", str(stats_path)],
        capture_output=True
    ).returncode == 1  # 0=无变化, 1=有变化
    if not has_changes:
        print(f"  - hook_stats 无变化，跳过 commit")
        return
    subprocess.run(["git", "commit", "-m", f"hook_stats: {node} — {total} triggers"],
                   capture_output=True, timeout=10)
    push = subprocess.run(["git", "push", "origin", "main"],
                          capture_output=True, text=True, timeout=20)

    if push.returncode == 0:
        print(f"  ✓ 已推送: .hook_stats/{node}.json ({total} triggers)")
    else:
        print(f"  ⚠ push 失败（网络问题?）: {push.stderr.strip()}")
        print(f"  数据已写入本地，下次 flush 自动重试")


def cmd_status():
    """查看今日日志"""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = LOCAL_LOG_DIR / f"raw_{date_str}.jsonl"
    if not log_path.exists():
        print("  今日无记录")
        return

    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    print(f"  今日日志: {log_path} ({len(lines)} 条)")
    for line in lines[-5:]:  # 最近 5 条
        try:
            r = json.loads(line)
            hit_str = f" → {r['hit']}" if r.get("hit") else ""
            print(f"    [{r['category']}] {r['ts'][:19]}{hit_str}")
        except json.JSONDecodeError:
            continue


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    node = NODE_ID

    # 解析 --node
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--node" and i + 1 < len(sys.argv):
            node = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    if cmd == "trigger":
        category = sys.argv[sys.argv.index("--category") + 1] if "--category" in sys.argv else ""
        hit = sys.argv[sys.argv.index("--hit") + 1] if "--hit" in sys.argv else None
        error = sys.argv[sys.argv.index("--error") + 1] if "--error" in sys.argv else None
        cmd_trigger(node, category, hit, error)
    elif cmd == "flush":
        cmd_flush(node)
    elif cmd == "status":
        cmd_status()
    elif cmd == "list-drafts":
        cmd_list_drafts()
    elif cmd == "promote" and len(sys.argv) >= 3:
        cmd_promote(sys.argv[2])
    elif cmd == "reject" and len(sys.argv) >= 3:
        cmd_reject(sys.argv[2])
    else:
        print(f"[error] 未知命令: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
