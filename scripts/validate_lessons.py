#!/usr/bin/env python3
"""
MisakaNet Lessons Validator
============================
验证 lessons/ 目录下所有 lesson 文件的 frontmatter 与结构是否合规。

用法:
  python3 scripts/validate_lessons.py
  python3 scripts/validate_lessons.py --path lessons/some_lesson.md
"""
import argparse
import io
import re
import sys
from pathlib import Path

# --- Windows console encoding fix ---------------------------------------
# On Windows, the default console code page (e.g. GBK/CP936) cannot encode
# many of the emoji characters used below (✅/❌/⚠), which raises
# UnicodeEncodeError when printed without PYTHONIOENCODING=utf-8 set.
# Reconfigure stdout/stderr to replace un-encodable characters instead of
# raising, so the script never crashes regardless of the console encoding.
# This is a no-op on platforms where the console already supports UTF-8
# (e.g. Linux/macOS), so behavior there is unchanged.
def _make_console_safe(stream):
    if stream is None:
        return stream
    try:
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
            return stream
    except Exception:
        pass
    try:
        buffer = getattr(stream, "buffer", None)
        if buffer is not None:
            return io.TextIOWrapper(
                buffer,
                encoding=getattr(stream, "encoding", None) or "utf-8",
                errors="replace",
                newline="",
            )
    except Exception:
        pass
    return stream


sys.stdout = _make_console_safe(sys.stdout)
sys.stderr = _make_console_safe(sys.stderr)
# -------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
LESSONS_DIR = PROJECT_ROOT / "lessons"

VALID_STATUSES = {"published", "draft", "rejected", "deprecated", "superseded", "needs_review"}
VALID_SOURCES = {"bootstrap", "realtime", "opus4.6"}

REQUIRED_FIELDS = ["title", "domain", "source", "status", "created"]


def _parse_frontmatter(raw: str) -> dict:
    """简易 YAML frontmatter 解析（不依赖 yaml 库）"""
    fields = {}
    for line in raw.strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip('"').strip("'")
    return fields


def validate_lesson(path: Path) -> list[str]:
    """验证单个 lesson 文件，返回错误列表"""
    errors = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"读取失败: {e}"]

    if not content.startswith("---"):
        return ["缺少 frontmatter (不以 --- 开头)"]

    parts = content.split("---", 2)
    if len(parts) < 3:
        return ["frontmatter 格式错误"]

    raw_fm = parts[1]
    body = parts[2].strip()

    fields = _parse_frontmatter(raw_fm)

    for field in REQUIRED_FIELDS:
        if field not in fields or not fields[field]:
            errors.append(f"缺少必填字段: {field}")

    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        errors.append(f"status 非法: {fields['status']} (允许: {','.join(sorted(VALID_STATUSES))})")
    if fields.get("source") and fields["source"] not in VALID_SOURCES:
        errors.append(f"source 非法: {fields['source']} (允许: {','.join(sorted(VALID_SOURCES))})")

    has_problem = bool(re.search(r"##\s*(?:问题|Problem)", body, re.IGNORECASE))
    has_fix = bool(re.search(r"##\s*(?:修复|Fix|方案|Solution)", body, re.IGNORECASE))
    has_verification = bool(re.search(r"##\s*(?:验证|Verification|测试|Test)", body, re.IGNORECASE))

    missing = []
    if not has_problem:
        missing.append("问题")
    if not has_fix:
        missing.append("修复")
    if not has_verification:
        missing.append("验证")

    if missing and fields.get("status") == "published":
        errors.append(f"published 状态但缺少: {'/'.join(missing)}")

    return errors


def main():
    parser = argparse.ArgumentParser(description="MisakaNet Lessons Validator")
    parser.add_argument("--path", default=None, help="只验证指定文件/目录（默认验证 lessons/ 全部）")
    args = parser.parse_args()

    if args.path:
        target = Path(args.path)
        files = [target] if target.is_file() else sorted(target.rglob("*.md"))
    else:
        if not LESSONS_DIR.exists():
            print(f"  ❌ lessons 目录不存在: {LESSONS_DIR}")
            sys.exit(1)
        files = sorted(LESSONS_DIR.rglob("*.md"))

    files = [f for f in files if f.name != "index.md"]

    total = 0
    failed = 0
    for f in files:
        total += 1
        errs = validate_lesson(f)
        if errs:
            failed += 1
            print(f"  ❌ {f}")
            for e in errs:
                print(f"      {e}")
        else:
            print(f"  ✅ {f}")

    print("=" * 50)
    if failed == 0:
        print(f"  ✅ 全部 {total} 条 lesson 验证通过")
    else:
        print(f"  ⚠ {total} 条中 {failed} 条有问题")
        sys.exit(1)


if __name__ == "__main__":
    main()
