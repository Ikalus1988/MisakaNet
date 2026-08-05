#!/usr/bin/env python3
"""
MisakaNet Inject to CLAUDE.md (cc 节点)
========================================
将 lessons 注入到 CLAUDE.md，供 Claude Code/cc-haha 节点读取。

用法:
  # 注入所有 lessons 到 CLAUDE.md
  python3 misakanet/scripts/inject_to_claude.py

  # 注入 lessons + 清理过期条目
  python3 misakanet/scripts/inject_to_claude.py --clean

效果:
  CLAUDE.md 底部自动维护一个 `## Cross-Node Lessons` 区块，
  每次更新时替换，不污染用户手动写的内容。
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent / ".." / ".."
LESSONS_DIR = Path(os.environ.get("LESSONS_DIR", REPO_ROOT / "lessons"))
HASH_STATE_FILE = Path(__file__).parent / ".inject_hash.json"


def collect_lessons():
    """读取所有 lesson 文件，返回文本摘要"""
    if not LESSONS_DIR.exists():
        return []

    lessons = []
    for f in sorted(LESSONS_DIR.glob("**/*.md")):
        if f.name == "index.md" or f.name == "templates":
            continue
        content = f.read_text(encoding="utf-8")
        title = ""
        domain = ""
        tags = []
        body = ""

        for line in content.split("\n"):
            if line.startswith("title:"):
                title = line.replace("title:", "").strip().strip('"\'')
            elif line.startswith("domain:"):
                domain = line.replace("domain:", "").strip().strip('"\'')
            elif line.startswith("tags:"):
                raw = line.replace("tags:", "").strip().strip("[]")
                tags = [t.strip().strip('"\'') for t in raw.split(",") if t.strip()]
            elif line == "---":
                continue
            elif not title or not line.startswith("---"):
                if body or (line.startswith("#") or line.startswith("##")):
                    body += line + "\n"

        # 提取第一段正文（去掉 YAML frontmatter）
        body_lines = []
        in_yaml = False
        for line in content.split("\n"):
            if line.strip() == "---":
                in_yaml = not in_yaml
                continue
            if not in_yaml:
                body_lines.append(line)
        clean_body = "\n".join(body_lines).strip()

        lessons.append({
            "title": title or f.name,
            "domain": domain,
            "tags": tags,
            "body": clean_body[:500],
        })

    return lessons


def _block_hash(block: str) -> str:
    """计算 lesson 区块的 SHA256（前 16 位）"""
    return hashlib.sha256(block.encode("utf-8")).hexdigest()[:16]


def _load_hash_state() -> dict:
    """加载上次哈希状态"""
    if HASH_STATE_FILE.exists():
        return json.loads(HASH_STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_hash_state(state: dict) -> None:
    """保存哈希状态"""
    HASH_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def inject_to_claudemd(lessons, clean=False):
    """写入 CLAUDE.md / AGENTS.md 共享区块"""
    claude_path = REPO_ROOT / "CLAUDE.md"
    agents_path = Path.home() / "CLAUDE.md"  # 用户根目录的 CLAUDE.md

    targets = []
    if claude_path.exists():
        targets.append(claude_path)
    if agents_path.exists():
        targets.append(agents_path)

    if not targets:
        print("[warn] 未找到 CLAUDE.md 或 AGENTS.md，跳过注入")
        # 至少创建一个
        claude_path.write_text("", encoding="utf-8")
        targets.append(claude_path)
        print(f"  → 创建 {claude_path}")

    block_marker_start = "<!-- MISAKANET_LESSONS_START -->"
    block_marker_end = "<!-- MISAKANET_LESSONS_END -->"

    static_header = "## 跨节点 Lessons (来自 MisakaNet)\n\n> 每次有价值的对话结束时，自问\"有什么值得跨节点共享？\"\n> 如果有，运行: `python3 scripts/queue_lesson.py --title \"...\" --domain \"...\" --content \"问题/修复/验证\"`\n> 或告诉用户：\"要把这个经验写成 lesson 吗？\"\n"

    lesson_lines = [block_marker_start, ""]
    for l in lessons:
        tags_str = " | ".join(l["tags"]) if l["tags"] else "—"
        lesson_lines.append(f"- **{l['title']}** [{l['domain']}] ({tags_str})")
        # 提取第一非空行作为摘要
        summary = ""
        for line in l["body"].split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("---"):
                summary = line[:120]
                break
        if summary:
            lesson_lines.append(f"  > {summary}")

    lesson_lines.append("")
    lesson_lines.append(block_marker_end)
    lesson_block = "\n".join(lesson_lines)

    for target in targets:
        existing = target.read_text(encoding="utf-8")

        if block_marker_start in existing:
            # 替换已有区块，但保留区块之前的 static_header
            pre_with_header = existing.split(block_marker_start)[0]
            # 如果 pre 没有 static_header，加上
            if static_header.strip() not in pre_with_header:
                pre_with_header = pre_with_header.rstrip() + "\n\n" + static_header
            post = existing.split(block_marker_end)[-1] if block_marker_end in existing else ""
            new_content = pre_with_header.strip() + "\n\n" + lesson_block + "\n\n" + post.strip()
        else:
            # 追加：加 header + block
            new_content = existing.rstrip() + "\n\n" + static_header + lesson_block + "\n"

        # Block 级 SHA256 比对：lesson 区块没变就不写文件
        block_hash = _block_hash(lesson_block)
        hash_state = _load_hash_state()
        if hash_state.get("last_hash") == block_hash:
            print(f"  ℹ️  跳过: {target} (lesson 区块无变化)")
            continue

        target.write_text(new_content, encoding="utf-8")
        print(f"  ✅ 注入: {target} ({len(lessons)} lessons)")

    # 更新哈希状态（所有 target 写完后）
    _save_hash_state({"last_hash": block_hash, "updated_at": datetime.now(timezone.utc).isoformat()})


def main():
    clean = "--clean" in sys.argv
    lessons = collect_lessons()
    print(f"=== MisakaNet Inject to CLAUDE.md ===")
    print(f"  lessons: {len(lessons)} 条")
    inject_to_claudemd(lessons, clean)
    print("=== done ===")


if __name__ == "__main__":
    main()
