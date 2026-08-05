#!/usr/bin/env python3
"""
MisakaNet Inject to AGENTS.md (OpenClaw Node7)
==============================================
将 lessons 注入到 OpenClaw 的 AGENTS.md，供 Node7 启动时读取。

触发条件（满足任一）：
  1. 每次会话启动时（AGENTS.md 已配置启动钩子）
  2. cron 定时同步（每小时）
  3. 手动调用：python3 scripts/inject_to_openclaw.py

效果：
  AGENTS.md 底部自动维护 `## MisakaNet Cross-Node Lessons` 区块。
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get("MISAKANET_ROOT", str(Path.home() / "MisakaNet")))
LESSONS_DIR = REPO_ROOT / "lessons"
HASH_FILE = Path(__file__).parent / ".inject_hash.json"


def collect_lessons():
    """读取所有 active 状态 lesson，返回摘要列表"""
    if not LESSONS_DIR.exists():
        return []

    lessons = []
    for f in sorted(LESSONS_DIR.glob("*.md")):
        if f.name in ("index.md", "templates"):
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue

        # 解析 frontmatter
        title = f.stem
        domain = "general"
        tags = []
        status = "active"

        lines = content.split("\n")
        in_fm = False
        body_lines = []
        for line in lines:
            if line.strip() == "---":
                in_fm = not in_fm
                continue
            if in_fm:
                if line.startswith("title:"):
                    title = line.replace("title:", "").strip().strip('"\'')
                elif line.startswith("domain:"):
                    domain = line.replace("domain:", "").strip().strip('"\'')
                elif line.startswith("tags:"):
                    raw = line.replace("tags:", "").strip().strip("[]")
                    tags = [t.strip().strip('"\'') for t in raw.split(",") if t.strip()]
                elif line.startswith("status:"):
                    status = line.replace("status:", "").strip().strip('"\'')
            else:
                body_lines.append(line)

        # 只展示 active/draft lessons
        if status not in ("active", "draft"):
            continue

        # 提取正文摘要（去掉 YAML 和 markdown 标题）
        clean_body = []
        for line in body_lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("- **"):
                clean_body.append(line)
                if len("\n".join(clean_body)) > 200:
                    break

        summary = "\n".join(clean_body)[:150].replace("\n", " ")

        lessons.append({
            "file": f.name,
            "title": title or f.stem,
            "domain": domain,
            "tags": tags,
            "status": status,
            "summary": summary,
        })

    return lessons


def _block_hash(lessons: list) -> str:
    h = hashlib.sha256()
    for l in lessons:
        h.update(f"{l['file']}|{l['title']}".encode())
    return h.hexdigest()[:16]


def inject():
    agents_md = Path.home() / "workspace/agent/workspace/AGENTS.md"
    if not agents_md.exists():
        agents_md = REPO_ROOT / "AGENTS.md"
    if not agents_md.exists():
        print("[warn] AGENTS.md not found")
        return

    lessons = collect_lessons()
    block_hash = _block_hash(lessons)

    # 检查是否变化
    if HASH_FILE.exists():
        last = json.loads(HASH_FILE.read_text(encoding="utf-8"))
        if last.get("hash") == block_hash:
            print(f"[skip] lessons 无变化 ({len(lessons)} lessons)")
            return

    MARKER_START = "<!-- MISAKANET_LESSONS_START -->"
    MARKER_END = "<!-- MISAKANET_LESSONS_END -->"

    existing = agents_md.read_text(encoding="utf-8")

    # 生成 lesson 列表
    block_lines = [MARKER_START, "", "## MisakaNet Cross-Node Lessons", ""]
    block_lines.append(f"> 来源: MisakaNet | 同步 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    block_lines.append(f"> 触发: 每次会话启动 / `python3 scripts/inject_to_openclaw.py`")
    block_lines.append("")

    for l in lessons:
        tags_str = ", ".join(l["tags"]) if l["tags"] else "—"
        block_lines.append(f"- **{l['title']}** [{l['domain']}] {l['status']}")
        block_lines.append(f"  `{' | '.join(l['tags'][:3])}`")
        if l["summary"]:
            block_lines.append(f"  > {l['summary'][:100]}...")

    block_lines.extend(["", MARKER_END, ""])

    # 替换或追加
    if MARKER_START in existing:
        pre = existing.split(MARKER_START)[0].rstrip()
        post = existing.split(MARKER_END)[-1].strip() if MARKER_END in existing else ""
        new_content = pre + "\n\n" + "\n".join(block_lines) + "\n\n" + post
    else:
        new_content = existing.rstrip() + "\n\n" + "\n".join(block_lines)

    agents_md.write_text(new_content, encoding="utf-8")
    HASH_FILE.write_text(json.dumps({"hash": block_hash, "updated": datetime.now().isoformat()}, ensure_ascii=False))

    print(f"[ok] AGENTS.md updated with {len(lessons)} lessons")


if __name__ == "__main__":
    inject()
