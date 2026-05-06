#!/usr/bin/env python3
"""
inject_to_claude.py — 将 lessons 标题摘要注入到 CLAUDE.md 的 MISAKANET_LESSONS 区块

用法:
  python3 inject_to_claude.py [--target path/to/CLAUDE.md]

如果不指定 --target，默认写入当前目录下的 CLAUDE.md。
支持多个 --target，每次调用写入所有指定文件。
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LESSONS_DIR = Path(os.environ.get("LESSONS_DIR",
                   Path(__file__).parent / ".." / ".." / "lessons"))


def _read_all_lessons() -> list[dict]:
    """读取所有 lesson 文件，返回文本摘要"""
    if not LESSONS_DIR.exists():
        return []

    lessons = []
    for f in sorted(LESSONS_DIR.glob("*.md")):
        if f.name == "index.md" or f.name == "templates":
            continue
        content = f.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        if fm and fm.get("title"):
            lessons.append({
                "title": fm["title"],
                "domain": fm.get("domain", ""),
                "tags": fm.get("tags", []),
                "content": content,
                "path": str(f.relative_to(LESSONS_DIR)),
            })
    return lessons


def _parse_frontmatter(text: str) -> dict | None:
    """解析 --- 包裹的 JSON frontmatter"""
    m = re.match(r"^---\s*\n(\{.*?\})\s*\n---", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _extract_summary(content: str, max_length: int = 120) -> str:
    """从 lesson 内容中提取第一非空行作为摘要"""
    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("---") and not stripped.startswith("{"):
            # 去掉标题行
            if stripped.startswith("#") or stripped.startswith("##"):
                continue
            # 截断
            if len(stripped) > max_length:
                return stripped[:max_length] + "…"
            return stripped
    return ""


def _block_hash(block: str) -> str:
    """计算 lesson 区块的 SHA256（前 16 位）"""
    return hashlib.sha256(block.encode("utf-8")).hexdigest()[:16]


def _load_hash_state() -> dict:
    """加载上次的哈希状态"""
    if HASH_STATE_FILE.exists():
        return json.loads(HASH_STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_hash_state(state: dict) -> None:
    """保存哈希状态"""
    HASH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _build_lesson_block(lessons: list[dict], targets: list[Path]) -> str:
    """构建完整的 lessons 区块"""
    block_marker_start = "<!-- MISAKANET_LESSONS_START -->"
    block_marker_end = "<!-- MISAKANET_LESSONS_END -->"

    static_header = (
        "## 跨节点 Lessons (来自 MisakaNet)\n\n"
        "> 每次有价值的对话结束时，自问\"有什么值得跨节点共享？\"\n"
        "> 如果有，运行: `python3 misakanet/scripts/queue_lesson.py "
        '--title "..." --domain "..." --content "问题/修复/验证"`\n'
        "> 或告诉用户：\"要把这个经验写成 lesson 吗？\"\n"
    )

    lesson_lines = [block_marker_start, ""]
    for l in lessons:
        tags_str = " | ".join(l["tags"]) if l["tags"] else "—"
        lesson_lines.append(f"- **{l['title']}** [{l['domain']}] ({tags_str})")
        summary = ""
        for line in l["content"].split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("---") and not stripped.startswith("{") and not stripped.startswith("#") and not stripped.startswith("##"):
                summary = stripped[:120] + ("…" if len(stripped) > 120 else "")
                break
        if summary:
            lesson_lines.append(f"  > {summary}")

    lesson_lines.append("")
    lesson_lines.append(block_marker_end)
    lesson_lines.append("")

    return "\n".join(lesson_lines)


def _update_claude(content: str, new_block: str) -> str:
    """替换 or 追加 MISAKANET_LESSONS 区块"""
    markers = [
        "<!-- MISAKANET_LESSONS_START -->",
        "<!-- MISAKANET_LESSONS_END -->",
    ]
    if markers[0] in content and markers[1] in content:
        before = content[: content.index(markers[0])]
        after = content[content.index(markers[1]) + len(markers[1]) :]
        return before.rstrip() + "\n\n" + new_block + after.lstrip()
    else:
        return content.rstrip() + "\n\n" + new_block


def main():
    global HASH_STATE_FILE
    HASH_STATE_FILE = Path(__file__).parent / ".inject_hash.json"

    targets = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--target" and i + 1 < len(sys.argv):
            targets.append(Path(sys.argv[i + 1]))
            i += 2
        else:
            print(f"[error] unknown param: {sys.argv[i]}", file=sys.stderr)
            sys.exit(1)

    if not targets:
        targets = [Path("CLAUDE.md")]

    lessons = _read_all_lessons()
    print(f"读取 {len(lessons)} 条 lesson")

    new_block = _build_lesson_block(lessons, targets)
    new_hash = _block_hash(new_block)

    old_state = _load_hash_state()

    for target in targets:
        tname = str(target)
        if old_state.get(tname) == new_hash:
            print(f"  → {tname}: 无变化，跳过")
            continue

        if target.exists():
            content = target.read_text(encoding="utf-8")
        else:
            content = ""
            print(f"  → 创建 {target}")

        updated = _update_claude(content, new_block)
        target.write_text(updated, encoding="utf-8")
        print(f"  → {tname}: 已更新 {len(lessons)} 条 lesson")

    _save_hash_state({**old_state, **{str(t): new_hash for t in targets}})
    print("完成")


if __name__ == "__main__":
    main()
