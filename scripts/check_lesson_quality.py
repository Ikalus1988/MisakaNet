#!/usr/bin/env python3
"""增强版 lesson 质量检查 — 命名/内容/异物检测.

验证项:
  1. frontmatter JSON schema 校验 (复用 validate_lessons.py)
  2. 文件名: 无中文, 无项目特定前缀 (cc-connect/ccswitch/codewhale/hermes 等)
  3. 内容: 无硬编码路径, 无项目特定用户/org (白名单除外)
  4. 内容: 含中文正文 → warning (建议英文)

用法:
  python3 scripts/check_lesson_quality.py <file>    # 检查单个文件
  python3 scripts/check_lesson_quality.py            # 检查所有 lessons
"""

import json, re, sys, os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"
CONTRIB = LESSONS / "contrib"
SCHEMA = REPO / "schemas" / "lesson.json"

# ─── 禁止的文件名前缀 ──────────────────────────────────────────
# 这些是项目特定工具名, 新 lesson 不得使用
BANNED_PREFIXES = [
    "cc-connect", "ccswitch", "codewhale", "deepseek-tui",
    "hermes-", "node_", "st2-", "node2-",
]

# ─── 禁止的内容模式 ────────────────────────────────────────────
# 白名单: MisakaNet, Ikalus1988 (项目名保留)
BANNED_CONTENT_PATTERNS = [
    # 硬编码路径
    (r'/mnt/c/Users/\w+/', 'hardcoded user path'),
    (r'C:\\Users\\\w+\\', 'hardcoded Windows user path'),
    # 特定用户名 (非 Ikalus1988)
    (r'\bzsxh1990\b', 'specific username zsxh1990 (use <user>)'),
    (r'\bcc_haha\b', 'specific agent name cc_haha (use <agent>)'),
]

# ─── 中文内容检测阈值 ──────────────────────────────────────────
CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')
CHINESE_LINE_THRESHOLD = 0.3  # 一行中超过30%中文字符即视为"中文行"


def check_filename(filepath: Path) -> list[str]:
    """检查文件名规范."""
    errors = []
    name = filepath.name

    # 是否有中文
    if CHINESE_RE.search(name):
        errors.append(f"FILENAME_CN: '{name}' contains Chinese characters — use English only")

    # 是否以禁止前缀开头
    for prefix in BANNED_PREFIXES:
        if name.startswith(prefix):
            errors.append(f"FILENAME_PREFIX: '{name}' starts with banned prefix '{prefix}' — use generic term")

    # 是否全小写 + 连字符
    stem = filepath.stem
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', stem):
        errors.append(f"FILENAME_FORMAT: '{name}' should be kebab-case (lowercase letters, numbers, hyphens)")

    return errors


def check_frontmatter(filepath: Path) -> list[str]:
    """检查 frontmatter JSON 合法性和必填字段."""
    errors = []
    content = filepath.read_text(encoding='utf-8')

    # 解析 frontmatter
    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return ["FRONTMATTER_MISSING: No frontmatter block found (must start with ---)"]

    raw = m.group(1).strip()
    try:
        fm = json.loads(raw)
    except json.JSONDecodeError as e:
        return [f"FRONTMATTER_JSON: Invalid JSON: {e}"]

    # 必填字段
    required = ["title", "domain", "status"]
    for field in required:
        if field not in fm:
            errors.append(f"FRONTMATTER_REQUIRED: Missing required field '{field}'")

    # 标题无中文
    title = fm.get("title", "")
    if CHINESE_RE.search(title):
        errors.append(f"FRONTMATTER_CN: Title contains Chinese: '{title}'")

    return errors


def check_content(filepath: Path) -> list[str]:
    """检查正文中的异物模式."""
    errors = []
    content = filepath.read_text(encoding='utf-8')

    for pattern, desc in BANNED_CONTENT_PATTERNS:
        if re.search(pattern, content):
            errors.append(f"CONTENT_BANNED: {desc} found in '{filepath.name}'")

    # 中文正文警告
    cn_lines = 0
    total_lines = 0
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('---') or line.startswith('{') or line.startswith('}'):
            continue
        total_lines += 1
        chinese_chars = len(CHINESE_RE.findall(line))
        if chinese_chars > 0 and chinese_chars / max(len(line), 1) > CHINESE_LINE_THRESHOLD:
            cn_lines += 1

    if total_lines > 5 and cn_lines / max(total_lines, 1) > 0.2:
        errors.append(f"CONTENT_CN_WARN: {cn_lines}/{total_lines} lines contain Chinese — consider English translation")

    return errors


def main():
    if len(sys.argv) > 1:
        targets = [Path(sys.argv[1])]
    else:
        targets = sorted(CONTRIB.glob("*.md")) + sorted(LESSONS.glob("*.md"))
        # 排除 index
        targets = [t for t in targets if t.name != "index.md"]

    total_errors = 0
    total_warnings = 0

    for fp in targets:
        file_errors = []
        file_warnings = []

        # 文件名检查
        for e in check_filename(fp):
            file_errors.append(e)

        # frontmatter 检查
        for e in check_frontmatter(fp):
            file_errors.append(e)

        # 内容检查
        for e in check_content(fp):
            if e.startswith("CONTENT_CN_WARN"):
                file_warnings.append(e)
            else:
                file_errors.append(e)

        if file_errors or file_warnings:
            print(f"\n{'='*60}")
            print(f"  {fp.relative_to(REPO)}")
            print(f"{'='*60}")
            for e in file_errors:
                print(f"  ❌ {e}")
                total_errors += 1
            for w in file_warnings:
                print(f"  ⚠️  {w}")
                total_warnings += 1

    print(f"\n{'='*60}")
    print(f"  总计: {total_errors} 错误, {total_warnings} 警告")
    print(f"{'='*60}")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
