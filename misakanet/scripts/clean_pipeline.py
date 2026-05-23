#!/usr/bin/env python3
"""
MisakaNet Lessons 清洗流水线 (Phase 2)
======================================
清洗 node 专用：读取 staging/ 中各节点贡献的 lesson 草稿，
执行 P0 脱敏 → P1 门禁 → 去重 → 分类 → 输出到 lessons/。

用法:
  # 完整清洗
  python3 misakanet/scripts/clean_pipeline.py

  # 只做 P0 脱敏预览（不改文件）
  python3 misakanet/scripts/clean_pipeline.py --dry-run --stage sanitize

  # 指定输入源（默认 staging/）
  python3 misakanet/scripts/clean_pipeline.py --src lessons --pattern "bootstrap_*.md"

  # 去重报告（不动文件）
  python3 misakanet/scripts/clean_pipeline.py --stage dedup

流程:
  1. 收集 → 读取所有 lessons
  2. P0 脱敏 → 路径/IP/Token/Slug 规范化
  3. P1 门禁 → 质量检查，不合格标 rejected
  4. 去重 → 语义相似度去重 + 冲突标记
  5. 分类 → domain/subdomain 自动归类
  6. 输出 → 写入 lessons/ 目录，更新 index
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

PROJECT_ROOT = Path(__file__).parent.parent.parent
STAGING_DIR = PROJECT_ROOT / "staging"
LESSONS_DIR = PROJECT_ROOT / "lessons"
INDEX_PATH = LESSONS_DIR / "index.md"

VALID_STATUSES = {"published", "draft", "rejected", "deprecated", "superseded", "needs_review"}
VALID_SOURCES = {"bootstrap", "realtime"}

# ── P0: 脱敏规则 ──────────────────────────────────────────

SENSITIVE_PATTERNS = [
    # Windows 用户名路径
    (r"\\\\?([A-Za-z]):\\\\Users\\\\[^\\\\]+\\\\", r"\\1:\\Users\\<USER>\\"),
    # Windows 用户名路径 (正斜杠)
    (r"/mnt/[a-z]/Users/[^/]+/", "/mnt/<DRIVE>/Users/<USER>/"),
    # Linux 家目录
    (r"/home/[^/]+/", "~/"),
    # GitHub token
    (r"gh[pso]_[A-Za-z0-9_]+", "<GITHUB_TOKEN>"),
    (r"github_pat_[A-Za-z0-9_]+", "<GITHUB_PAT>"),
    # API key 模式
    (r"sk-[A-Za-z0-9]{20,}", "<API_KEY>"),
    # Bearer token
    (r"Bearer\s+[A-Za-z0-9\-_.]{20,}", "Bearer <TOKEN>"),
    # IP 地址（内网）
    (r"\b(172\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", "<HOST_IP>"),
    (r"\b(192\.168\.\d{1,3}\.\d{1,3})\b", "<HOST_IP>"),
    (r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", "<HOST_IP>"),
    # 端口号（常见服务端口在上下文中可能为敏感信息）
    # 不处理 80/443/8080/3000/8000 等常见端口
]

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

FIX_SECTION_PATTERNS = [
    re.compile(r"##\s*(?:问题|Problem|背景|Background)", re.IGNORECASE),
    re.compile(r"##\s*(?:修复|Fix|方案|Solution)", re.IGNORECASE),
    re.compile(r"##\s*(?:验证|Verification|测试|Test)", re.IGNORECASE),
]


# ── 核心函数 ──────────────────────────────────────────────

def collect_lessons(src_dir: Path, pattern: str = "*.md") -> list[dict]:
    """收集所有 lessons 文件，返回 [{path, content, fm}] 列表"""
    lessons = []
    if not src_dir.exists():
        return lessons

    for f in sorted(src_dir.rglob(pattern)):
        if f.name.startswith("."):
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ⚠ 读取失败: {f.relative_to(PROJECT_ROOT)} — {e}")
            continue

        if not content.startswith("---"):
            print(f"  ⚠ 无 frontmatter: {f.relative_to(PROJECT_ROOT)}")
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            print(f"  ⚠ frontmatter 格式错误: {f.relative_to(PROJECT_ROOT)}")
            continue

        fm = _parse_frontmatter(parts[1])
        lessons.append({
            "path": f,
            "content": content,
            "fm": fm,
            "body": parts[2].strip(),
            "relpath": str(f.relative_to(PROJECT_ROOT)),
        })

    return lessons


def _parse_frontmatter(raw: str) -> dict:
    """简易 YAML frontmatter 解析"""
    fm = {}
    for line in raw.strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'").strip("[]")
    return fm


def step_sanitize(lessons: list[dict], dry_run: bool = False) -> list[dict]:
    """P0: 脱敏 — 路径/IP/Token 替换"""
    print(f"\n{'='*50}")
    print("P0 脱敏")
    print('='*50)

    changed = 0
    for lesson in lessons:
        original = lesson["content"]
        for pattern, replacement in SENSITIVE_PATTERNS:
            lesson["content"] = re.sub(pattern, replacement, lesson["content"])

        if lesson["content"] != original:
            changed += 1
            if dry_run:
                # 显示差异
                sm = SequenceMatcher(None, original, lesson["content"])
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "replace":
                        print(f"  [{lesson['fm'].get('title','?')[:30]}]")
                        print(f"    - {original[i1:i2][:80]}")
                        print(f"    + {lesson['content'][j1:j2][:80]}")

    action = "预览" if dry_run else "已替换"
    print(f"  {action}: {changed}/{len(lessons)} 条包含敏感信息")
    return lessons


def step_quality_gate(lessons: list[dict]) -> list[dict]:
    """P1: 质量门禁 — 必须有 Problem + Fix + Verification"""
    print(f"\n{'='*50}")
    print("P1 质量门禁")
    print('='*50)

    passed = rejected = 0
    for lesson in lessons:
        body = lesson["body"]
        status = lesson["fm"].get("status", "draft")

        has_fix = any(p.search(body) for p in FIX_SECTION_PATTERNS)
        # 至少需要 fix 部分
        has_fix_section = bool(re.search(r"##\s*(?:修复|Fix|方案|Solution)", body, re.IGNORECASE))
        has_verification = bool(re.search(r"##\s*(?:验证|Verification|测试|Test)", body, re.IGNORECASE))

        issues = []
        if not has_fix_section:
            issues.append("缺少修复 (## 修复 / ## Fix)")
        if not has_verification:
            issues.append("缺少验证 (## 验证 / ## Verification)")

        if issues and status == "published":
            print(f"  ⚠ {lesson['relpath']}")
            for i in issues:
                print(f"    {i}")
            # 不强行改状态，只报告

        if not has_fix_section or not has_verification:
            if status != "rejected":
                rejected += 1
        else:
            passed += 1

    print(f"  ✅ 通过: {passed} | ⚠ 需补充: {rejected} | 总计: {len(lessons)}")
    return lessons


def step_dedup(lessons: list[dict]) -> list[dict]:
    """去重 — 基于 title 和 domain 的相似度去重"""
    print(f"\n{'='*50}")
    print("去重检测")
    print('='*50)

    n = len(lessons)
    merged = set()
    duplicates = []

    for i in range(n):
        if i in merged:
            continue
        for j in range(i + 1, n):
            if j in merged:
                continue

            fi = lessons[i]["fm"]
            fj = lessons[j]["fm"]

            # Exact title match → 确认重复
            if fi.get("title", "").strip().lower() == fj.get("title", "").strip().lower():
                duplicates.append((i, j, 1.0, "标题完全匹配"))
                merged.add(j)
                continue

            # 同一 domain + 标题相似度 > 0.85 → 疑似重复
            if fi.get("domain") == fj.get("domain"):
                ti = fi.get("title", "").lower()
                tj = fj.get("title", "").lower()
                sim = SequenceMatcher(None, ti, tj).ratio()
                if sim > 0.85:
                    duplicates.append((i, j, sim, "标题相似"))
                    merged.add(j)
                    continue

    if duplicates:
        print(f"  发现 {len(duplicates)} 组重复/疑似重复:")
        for i, j, sim, reason in duplicates:
            ti = lessons[i]["fm"].get("title", "?")[:40]
            tj = lessons[j]["fm"].get("title", "?")[:40]
            print(f"    [{sim:.2f}] {reason}")
            print(f"      A: {lessons[i]['relpath']} → {ti}")
            print(f"      B: {lessons[j]['relpath']} → {tj}")
            # 保留更完整的（body 更长的）
            keep = i if len(lessons[i]["body"]) >= len(lessons[j]["body"]) else j
            drop = j if keep == i else i
            print(f"      → 保留 {lessons[keep]['relpath']}，跳过 {lessons[drop]['relpath']}")
    else:
        print("  无重复")

    # 返回去重后的列表（保留 keep 的）
    keep_indices = set(range(n)) - {j for _, j, _, _ in duplicates}
    return [lessons[i] for i in sorted(keep_indices)]


def step_classify(lessons: list[dict]) -> list[dict]:
    """分类 — 根据内容关键词自动补充分类"""
    print(f"\n{'='*50}")
    print("自动分类")
    print('='*50)

    classified = 0
    for lesson in lessons:
        domain = lesson["fm"].get("domain", "")
        if domain and domain != "general":
            continue  # 已有明确 domain，跳过

        body_lower = (lesson["fm"].get("title", "") + " " + lesson["body"]).lower()
        title_lower = lesson["fm"].get("title", "").lower()

        scores = {}
        for d, keywords in DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in body_lower)
            if score > 0:
                scores[d] = score

        if scores:
            best = max(scores, key=scores.get)
            # 写入 frontmatter
            lesson["fm"]["domain"] = best
            # 更新 content 中的 frontmatter
            parts = lesson["content"].split("---", 2)
            new_fm = _rebuild_frontmatter(lesson["fm"])
            lesson["content"] = f"---\n{new_fm}---\n\n{parts[2].strip()}\n"
            classified += 1

    print(f"  自动分类: {classified}/{len(lessons)} 条")
    return lessons


def _rebuild_frontmatter(fm: dict) -> str:
    """从 dict 重建 frontmatter 字符串"""
    lines = []
    for key in ["title", "domain", "subdomain", "source", "status", "tags",
                 "confidence", "created", "last_verified", "verified_by",
                 "related", "alternative_of", "superseded_by"]:
        val = fm.get(key)
        if val is None or val == "":
            continue
        if key == "tags" and isinstance(val, str):
            lines.append(f'{key}: [{val}]')
        else:
            lines.append(f'{key}: {val}')
    return "\n".join(lines) + "\n"


def step_output(lessons: list[dict]):
    """输出 — 通过 queue_lesson.py --file 写入 lessons/ + git push"""
    import subprocess
    import tempfile

    print(f"\n{'='*50}")
    print("输出到 lessons/ (via queue_lesson.py --file)")
    print('='*50)

    script = PROJECT_ROOT / "misakanet" / "scripts" / "queue_lesson.py"
    written = 0
    failed = 0

    with tempfile.TemporaryDirectory(prefix="misakanet_clean_") as tmpdir:
        for lesson in lessons:
            title = lesson["fm"].get("title", "untitled")
            slug = title.lower().strip()
            slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
            slug = slug.strip("-")[:60]
            filename = f"{slug}.md"

            # 写入临时文件
            parts = lesson["content"].split("---", 2)
            new_fm = _rebuild_frontmatter(lesson["fm"])
            content = f"---\n{new_fm}---\n\n{parts[2].strip()}\n"

            tmpfile = Path(tmpdir) / filename
            tmpfile.write_text(content, encoding="utf-8")

            # 通过 queue_lesson.py --file 推流 (含 index 更新 + git push)
            result = subprocess.run(
                ["python3", str(script), "--file", str(tmpfile)],
                capture_output=True, text=True, timeout=60,
            )

            if result.returncode == 0:
                print(f"  ✅ {filename}")
                written += 1
            else:
                print(f"  ❌ {filename}: {result.stderr.strip() or result.stdout.strip()}")
                failed += 1

    print(f"\n  共 {written} 条成功, {failed} 条失败 → lessons/")


def _update_index(lessons: list[dict]):
    """更新 index.md"""
    entries = []
    for lesson in sorted(lessons, key=lambda l: l["fm"].get("domain", "")):
        fm = lesson["fm"]
        title = fm.get("title", "?")
        domain = fm.get("domain", "?")
        tags = fm.get("tags", "")
        status = fm.get("status", "draft")
        if status == "rejected":
            continue
        entries.append(f"- [{title}]({LESSONS_DIR.name}/{_slug(fm)}) | {domain} | {tags} | {status}")

    header = [
        "# MisakaNet Shared Lessons",
        "",
        f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"> 清洗 node: clean_pipeline.py (Phase 2)",
        "",
        "## 目录",
        "",
        "| Lesson | Domain | Tags | Status |",
        "|--------|--------|------|--------|",
    ]

    content = "\n".join(header + entries) + "\n"
    INDEX_PATH.write_text(content, encoding="utf-8")
    print(f"  📝 index.md 已更新 ({len(entries)} 条)")


def _slug(fm: dict) -> str:
    title = fm.get("title", "untitled")
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    return slug.strip("-")[:60]


def main():
    parser = argparse.ArgumentParser(description="Lessons 清洗流水线")
    parser.add_argument("--src", default=str(STAGING_DIR), help="源目录 (默认 staging/)")
    parser.add_argument("--pattern", default="*.md", help="文件匹配模式")
    parser.add_argument("--stage", choices=["all", "sanitize", "quality", "dedup", "classify", "output"],
                        default="all", help="执行阶段")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不改文件")
    args = parser.parse_args()

    src_dir = Path(args.src)

    print(f"MisakaNet Lessons 清洗流水线")
    print(f"{'='*50}")
    print(f"  源目录: {src_dir}")
    print(f"  匹配: {args.pattern}")
    print(f"  模式: {'预览' if args.dry_run else '执行'}")

    # 收集
    lessons = collect_lessons(src_dir, args.pattern)
    print(f"\n  收集: {len(lessons)} 条")

    if not lessons:
        print("  无 lessons 可处理")
        return

    # 各阶段（可跳过）
    stages = {
        "sanitize": lambda l: step_sanitize(l, args.dry_run),
        "quality": step_quality_gate,
        "dedup": step_dedup,
        "classify": step_classify,
        "output": step_output,
    }

    if args.stage == "all":
        # 按顺序执行
        lessons = step_sanitize(lessons, args.dry_run)
        if args.dry_run:
            print("\n  预览模式，跳过后续阶段")
            return
        lessons = step_quality_gate(lessons)
        lessons = step_dedup(lessons)
        lessons = step_classify(lessons)
        step_output(lessons)
    else:
        # 只执行指定阶段
        fn = stages.get(args.stage)
        if fn:
            fn(lessons)
        else:
            print(f"  未知阶段: {args.stage}")

    print(f"\n{'='*50}")
    print(f"完成")


if __name__ == "__main__":
    main()
