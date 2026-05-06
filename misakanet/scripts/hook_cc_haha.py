#!/usr/bin/env python3
"""
cc-haha 专属 Lesson 生成器
==========================
cc-haha 的 PostToolUseFailure hook 在 Bash 执行失败时调用此脚本。
设计原则：不修改通用工具（queue_lesson.py / draft_reminder.py / queue_hook_stats.py），
         cc-haha 的专属逻辑独立在此。

用法 (供 cc-haha hook 调用):
  python3 misakanet/scripts/hook_cc_haha.py \\
    --category network \\
    --error "Connection refused to api.llm.mioffice.cn:443" \\
    --command "curl -s https://api.llm.mioffice.cn/v1/chat/completions"

参数:
  --category  分类: network|pip|permission|disk|package_conflict|model_output
  --error     错误信息
  --command   执行的命令（可选，帮助复现）
  --dry-run   只打印不写入

流程:
  1. 解析 hook 参数
  2. 生成有意义的 title + 标准 lesson 内容
  3. 调 queue_lesson.write_lesson() 直接写入（published 状态）
  4. 调 queue_hook_stats.cmd_trigger() 记录统计
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 项目根
REPO_ROOT = Path(__file__).parent / ".." / ".."
sys.path.insert(0, str(REPO_ROOT))

from misakanet.scripts.queue_lesson import write_lesson
from misakanet.scripts.queue_hook_stats import cmd_trigger, CATEGORIES

NODE_ID = "cc_haha"

# 分类 → 中文描述映射
CATEGORY_LABELS = {
    "network": "网络连接",
    "pip": "Python 包安装",
    "permission": "权限",
    "disk": "磁盘空间",
    "package_conflict": "包冲突",
    "model_output": "模型输出异常",
}


def _truncate_error(error: str, max_len: int = 200) -> str:
    """截断错误信息，保留关键部分"""
    if len(error) <= max_len:
        return error
    return error[:max_len] + "...(截断)"


def _extract_key_from_error(error: str) -> str:
    """从错误信息中提取关键标识，用于去重/标签"""
    # 常见模式：Connection refused, Timeout, 404, 403, 500, No space left
    patterns = [
        (r"((?:Connection\s+refused|Timeout|No\s+route\s+to\s+host|Name\s+or\s+service\s+not\s+known|resolve\s+hostname))", "network"),
        (r"((?:No\s+space\s+left\s+on\s+device|Disk\s+quota\s+exceeded))", "disk"),
        (r"((?:Permission\s+denied|EACCES|EACCESS))", "permission"),
        (r"(HTTP\s+[45]\d\d)", "http"),
        (r"(pip\s+(?:install|download|uninstall)\s+\S+)", "pip"),
    ]
    for pat, tag in patterns:
        m = re.search(pat, error, re.IGNORECASE)
        if m:
            return f"{tag}:{m.group(1)}"
    return ""


def generate_title(category: str, error: str) -> str:
    """生成有辨识度的标题"""
    label = CATEGORY_LABELS.get(category, category)
    # 截取错误中可读的部分
    key = _extract_key_from_error(error)
    if key:
        return f"[cc-haha] {label} 错误 — {key}"
    # 后备：用 error 前 40 字
    short = _truncate_error(error.strip(), 60).replace("\n", " ")
    return f"[cc-haha] {label} 错误 — {short}"


def generate_content(category: str, error: str, command: str = "") -> str:
    """生成标准的 lesson 内容"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    label = CATEGORY_LABELS.get(category, category)

    parts = [
        f"## 问题",
        f"",
        f"自动捕获于 cc-haha hook（时间: {now}）。",
        f"",
        f"**分类:** {label}",
        f"",
    ]
    if command:
        parts.append(f"**命令:**")
        parts.append(f"```bash")
        parts.append(f"{command}")
        parts.append(f"```")
        parts.append(f"")

    parts.extend([
        f"**错误信息:**",
        f"```",
        f"{error}",
        f"```",
        f"",
        f"## 根因",
        f"",
        f"（待补充 — hook 自动捕获，需人工分析根因）",
        f"",
        f"## 修复",
        f"",
        f"（待补充 — 请补充修复步骤）",
        f"",
        f"## 验证",
        f"",
        f"（待补充 — 请补充验证方式）",
    ])
    return "\n".join(parts)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="cc-haha lesson 生成器")
    parser.add_argument("--category", required=True,
                        choices=CATEGORIES,
                        help=f"错误分类: {', '.join(CATEGORIES)}")
    parser.add_argument("--error", required=True, help="错误信息")
    parser.add_argument("--command", default="", help="触发错误的命令（可选）")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")

    args = parser.parse_args()

    error = args.error
    command = args.command
    category = args.category

    title = generate_title(category, error)
    content = generate_content(category, error, command)

    print(f"=== cc-haha Lesson Generator ===")
    print(f"  category: {category}")
    print(f"  title:    {title}")
    print(f"  dry-run:  {args.dry_run}")

    if args.dry_run:
        print(f"\n--- 生成的 content ---")
        print(content)
        print(f"--- 结束 ---")
        return

    # 写入 lesson（直接 published，hook 捕获的错误应该立即入库）
    write_lesson(
        title=title,
        domain=category,
        tags=[f"cc-haha", f"hook-auto", category, _extract_key_from_error(error)],
        content=content,
        source=NODE_ID,
        status="published",
    )
    print(f"  ✅ lesson 已写入")

    # 记录 hook 统计（用于飞书推送和趋势分析）
    # 注意：此调用需要 queue_hook_stats.py 在项目路径中
    try:
        hit_key = _extract_key_from_error(error)
        cmd_trigger(
            node=NODE_ID,
            category=category,
            hit=hit_key or None,
            error=error,
        )
        print(f"  📊 hook stats 已记录")
    except Exception as e:
        print(f"  ⚠ hook stats 记录失败 (不影响 lesson): {e}")

    print("=== done ===")


if __name__ == "__main__":
    main()
