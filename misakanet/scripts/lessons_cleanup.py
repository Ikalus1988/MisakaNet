#!/usr/bin/env python3
"""
MisakaNet Lessons Cleanup
=========================
清理 lessons/ 目录：归档 dump、补 frontmatter、规范化元数据、重建索引。

用法:
  python3 misakanet/scripts/lessons_cleanup.py manifest       # 清单预览
  python3 misakanet/scripts/lessons_cleanup.py all --dry-run  # 预览所有变更
  python3 misakanet/scripts/lessons_cleanup.py all            # 执行清理
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
LESSONS_DIR = PROJECT_ROOT / "lessons"
ARCHIVE_DIR = LESSONS_DIR / "_archive"
INDEX_PATH = LESSONS_DIR / "index.md"
JSON_PATH = PROJECT_ROOT / "lessons.json"

# ── Domain 映射 ──────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "rag": ["chromadb", "embedding", "retrieval", "vector", "分块", "chunk", "semantic", "索引"],
    "fanuc": ["fanuc", "karel", "kl\\.", "robot", "报警", "alarm", "srvo", "r-30i", "r-2000"],
    "feishu": ["feishu", "飞书", "webhook", "block api", "card", "消息卡片"],
    "devops": ["wsl", "pip", "git", "ssh", "cron", "bash", "shell", "环境", "install"],
    "docker": ["docker", "dockerfile", "docker-compose", "container", "image", "buildx"],
    "hub": ["hub", "poller", "graph", "仲裁", "节点", "sync", "a2a"],
    "claude": ["claude", "hermes", "cc-haha", "claude code", "session", "artifact"],
    "network": ["proxy", "代理", "tls", "ssl", "dns", "connect", "超时", "timeout"],
}

DOMAIN_REMAP = {
    "rag-retrieval": "rag",
    "filesystem-permission": "devops",
    "dependency-install": "devops",
    "disk-space": "devops",
    "system": "devops",
    "hermes-setup": "devops",
    "model-output": "claude",
    "ailysw": "feishu",
    "feishu-integration": "feishu",
}

STATUS_REMAP = {"active": "published"}

# 文件名 → domain 推断（用于无 frontmatter 的 skill-* 文件）
FILENAME_DOMAIN_HINTS = {
    "skill-feishu": "feishu",
    "skill-task-board": "feishu",
    "skill-edoc": "rag",
    "skill-rag": "rag",
    "skill-dogfood": "claude",
    "browser-harness": "devops",
}

# ── Frontmatter 解析 ─────────────────────────────────────

def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter，返回 dict"""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'").strip("[]")
    return fm


def rebuild_frontmatter(fm: dict) -> str:
    """从 dict 重建 YAML frontmatter 字符串"""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f'{k}: [{", ".join(v)}]')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines)


# ── Phase 1: 归档残留 dump ───────────────────────────────

def phase_archive(dry_run=False):
    """归档主目录中的对话 dump 文件"""
    print("\n" + "=" * 50)
    print("Phase 1: 归档残留 dump")
    print("=" * 50)

    # 已知的 dump 文件（在主目录中仍存在的）
    dump_patterns = [
        "cc-haha的命令行已正常",
    ]

    moved = 0
    for f in sorted(LESSONS_DIR.glob("*.md")):
        if f.name == "index.md":
            continue
        for pat in dump_patterns:
            if pat in f.name:
                dest = ARCHIVE_DIR / "hook-raw" / f.name
                if dry_run:
                    print(f"  [dry-run] {f.name} → _archive/hook-raw/")
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(dest))
                    print(f"  ✓ {f.name} → _archive/hook-raw/")
                moved += 1
                break

    print(f"  归档: {moved} 个文件")
    return moved


# ── Phase 2: 补 frontmatter ─────────────────────────────

def infer_domain(filename: str, content: str) -> str:
    """从文件名和内容推断 domain"""
    fn_lower = filename.lower()
    for prefix, domain in FILENAME_DOMAIN_HINTS.items():
        if prefix in fn_lower:
            return domain

    # 按内容关键词匹配
    content_lower = content.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in content_lower)
        if score > 0:
            scores[domain] = score

    if scores:
        return max(scores, key=scores.get)
    return "devops"


def phase_frontmatter(dry_run=False):
    """为缺少 frontmatter 的文件添加"""
    print("\n" + "=" * 50)
    print("Phase 2: 补 frontmatter")
    print("=" * 50)

    added = 0
    for f in sorted(LESSONS_DIR.glob("*.md")):
        if f.name == "index.md":
            continue

        content = f.read_text(encoding="utf-8")
        if content.startswith("---"):
            continue

        # 提取标题：第一个 # heading 或文件名
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else f.stem.replace("-", " ").replace("_", " ")

        domain = infer_domain(f.name, content)
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")

        fm = {
            "title": title,
            "domain": domain,
            "source": "skill-harvest",
            "status": "draft",
            "confidence": 0.6,
            "created": mtime,
        }

        new_content = rebuild_frontmatter(fm) + "\n\n" + content

        if dry_run:
            print(f"  [dry-run] {f.name}: domain={domain}, title={title[:40]}")
        else:
            f.write_text(new_content, encoding="utf-8")
            print(f"  ✓ {f.name}: domain={domain}")
        added += 1

    print(f"  补充: {added} 个文件")
    return added


# ── Phase 3: 规范化 domain 和 status ─────────────────────

def phase_normalize(dry_run=False):
    """规范化 frontmatter 中的 domain 和 status"""
    print("\n" + "=" * 50)
    print("Phase 3: 规范化 domain / status")
    print("=" * 50)

    domain_changed = 0
    status_changed = 0

    for f in sorted(LESSONS_DIR.glob("*.md")):
        if f.name == "index.md":
            continue

        content = f.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue

        fm = parse_frontmatter(content)
        modified = False

        # Domain 规范化
        old_domain = fm.get("domain", "")
        if old_domain in DOMAIN_REMAP:
            new_domain = DOMAIN_REMAP[old_domain]
            fm["domain"] = new_domain
            modified = True
            domain_changed += 1
            if dry_run:
                print(f"  [dry-run] {f.name}: domain {old_domain} → {new_domain}")
            else:
                print(f"  ✓ domain: {f.name}: {old_domain} → {new_domain}")

        # Status 规范化
        old_status = fm.get("status", "")
        if old_status in STATUS_REMAP:
            new_status = STATUS_REMAP[old_status]
            fm["status"] = new_status
            modified = True
            status_changed += 1
            if dry_run:
                print(f"  [dry-run] {f.name}: status {old_status} → {new_status}")
            else:
                print(f"  ✓ status: {f.name}: {old_status} → {new_status}")

        if modified and not dry_run:
            parts = content.split("---", 2)
            new_content = rebuild_frontmatter(fm) + "\n" + parts[2]
            f.write_text(new_content, encoding="utf-8")

    print(f"  domain 规范化: {domain_changed} 个文件")
    print(f"  status 规范化: {status_changed} 个文件")
    return domain_changed + status_changed


# ── Phase 4: 重建 index.md ──────────────────────────────

def phase_rebuild_index(dry_run=False):
    """从 lessons/*.md 重建 index.md"""
    print("\n" + "=" * 50)
    print("Phase 4: 重建 index.md")
    print("=" * 50)

    entries = []
    for f in sorted(LESSONS_DIR.glob("*.md")):
        if f.name == "index.md":
            continue

        content = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)

        title = fm.get("title", f.stem)
        domain = fm.get("domain", "uncategorized")
        tags_raw = fm.get("tags", "")
        source = fm.get("source", fm.get("status", ""))
        status = fm.get("status", "")

        # 格式化 tags
        if tags_raw and not tags_raw.startswith('"'):
            tags_str = tags_raw
        elif tags_raw:
            tags_str = tags_raw
        else:
            tags_str = ""

        entries.append({
            "title": title,
            "domain": domain,
            "tags": tags_str,
            "source": source if source else status,
            "filename": f.name,
        })

    # 按 domain 分组排序
    entries.sort(key=lambda e: (e["domain"], e["title"]))

    # 生成 index.md
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# MisakaNet Shared Lessons",
        "",
        f"> 最后更新: {now} | 来源: lessons_cleanup.py",
        "",
        "每条 lesson 包含踩坑记录、修复方法和验证方式，跨节点自动同步。",
        "",
        "## 目录",
        "",
        "| Lesson | Domain | Tags | Source |",
        "|--------|--------|------|--------|",
    ]

    for e in entries:
        link = f"[{e['title']}]({e['filename']})"
        lines.append(f"- {link} | {e['domain']} | {e['tags']} | {e['source']}")

    lines.append("")

    new_index = "\n".join(lines)

    if dry_run:
        print(f"  [dry-run] 将生成 {len(entries)} 条索引")
        print(f"  当前 index 条目数: {sum(1 for l in INDEX_PATH.read_text().splitlines() if l.strip().startswith('- ['))}")
    else:
        INDEX_PATH.write_text(new_index, encoding="utf-8")
        print(f"  ✓ 生成 {len(entries)} 条索引")

    return len(entries)


# ── Phase 5: 重建 lessons.json ───────────────────────────

def phase_rebuild_json(dry_run=False):
    """从 lessons/*.md 重建 lessons.json"""
    print("\n" + "=" * 50)
    print("Phase 5: 重建 lessons.json")
    print("=" * 50)

    entries = []
    for f in sorted(LESSONS_DIR.glob("*.md")):
        if f.name == "index.md":
            continue

        content = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        body = ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2].strip()

        # 提取摘要：第一个非空段落
        summary = ""
        for para in body.split("\n\n"):
            para = para.strip()
            if para and not para.startswith("#") and not para.startswith("```"):
                summary = para[:200]
                break

        title = fm.get("title", f.stem)
        domain = fm.get("domain", "uncategorized")
        tags_raw = fm.get("tags", "")

        # 解析 tags
        if isinstance(tags_raw, str):
            tags = [t.strip().strip('"') for t in tags_raw.split(",") if t.strip()]
        else:
            tags = tags_raw if isinstance(tags_raw, list) else []

        entries.append({
            "id": f.stem,
            "title": title,
            "domain": domain,
            "tags": tags,
            "summary": summary,
            "url": f"lessons/{f.name}",
            "updated": fm.get("created", fm.get("updated", "")),
            "status": fm.get("status", "draft"),
        })

    if dry_run:
        print(f"  [dry-run] 将生成 {len(entries)} 条 JSON")
        unc = sum(1 for e in entries if e["domain"] == "uncategorized")
        print(f"  其中 uncategorized: {unc}")
    else:
        JSON_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ 生成 {len(entries)} 条 JSON")
        unc = sum(1 for e in entries if e["domain"] == "uncategorized")
        print(f"  uncategorized: {unc}")

    return len(entries)


# ── 主入口 ───────────────────────────────────────────────

def cmd_manifest():
    """生成清理清单"""
    print("MisakaNet Lessons 清理清单")
    print("=" * 50)

    # 统计主目录
    main_files = [f for f in LESSONS_DIR.glob("*.md") if f.name != "index.md"]
    no_fm = [f for f in main_files if not f.read_text(encoding="utf-8").startswith("---")]

    # 统计 status
    active_count = 0
    domain_remap_count = 0
    for f in main_files:
        content = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        if fm.get("status") == "active":
            active_count += 1
        if fm.get("domain", "") in DOMAIN_REMAP:
            domain_remap_count += 1

    # 统计 index
    index_content = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
    index_links = re.findall(r"\]\(([^)]+)\)", index_content)
    main_filenames = {f.name for f in main_files}
    stale_links = [l for l in index_links if not l.startswith("http") and Path(l).name not in main_filenames]
    unindexed = [f.name for f in main_files if f.name not in {Path(l).name for l in index_links}]

    print(f"\n主目录文件: {len(main_files)}")
    print(f"缺少 frontmatter: {len(no_fm)}")
    print(f"status: active (需规范化): {active_count}")
    print(f"domain 需映射: {domain_remap_count}")
    print(f"index 失效链接: {len(stale_links)}")
    print(f"未索引文件: {len(unindexed)}")

    if no_fm:
        print(f"\n无 frontmatter 文件:")
        for f in no_fm:
            print(f"  - {f.name}")


def cmd_all(dry_run=False):
    """执行所有清理阶段"""
    mode = "预览" if dry_run else "执行"
    print(f"Lessons 清理 — {mode}模式")
    print("=" * 50)

    phase_archive(dry_run)
    phase_frontmatter(dry_run)
    phase_normalize(dry_run)
    phase_rebuild_index(dry_run)
    phase_rebuild_json(dry_run)

    print("\n" + "=" * 50)
    if dry_run:
        print("预览完成。去掉 --dry-run 执行实际清理。")
    else:
        print("清理完成。请运行验证命令确认结果。")


def main():
    parser = argparse.ArgumentParser(description="MisakaNet Lessons Cleanup")
    parser.add_argument("command", choices=["manifest", "all"],
                        help="manifest=清单预览, all=执行清理")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不修改文件")
    args = parser.parse_args()

    if args.command == "manifest":
        cmd_manifest()
    elif args.command == "all":
        cmd_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
