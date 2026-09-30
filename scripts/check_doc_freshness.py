#!/usr/bin/env python3
"""Check that managed docs don't carry stale numbers contradicting SSOT.

Scans ROADMAP.md, README files, and other managed surfaces for literal
lesson/domain counts that don't match `sync_lesson_count.py --check`.

Distinguishes:
  - "Current" sections: stale = FAIL
  - "Historical" sections (after section markers): stale = WARN
  - Badge/shield.io lines: always skipped

Usage:
    python3 scripts/check_doc_freshness.py          # report mismatches
    python3 scripts/check_doc_freshness.py --check   # non-zero exit if errors
    python3 scripts/check_doc_freshness.py --json    # JSON output
    python3 scripts/check_doc_freshness.py --reverse-test  # verify detection works

Part of #2082: freshness gate for managed documentation.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MANAGED_FILES = [
    "ROADMAP.md",
    "README.md",
    "README.zh-CN.md",
    "README.ja.md",
    "docs/maintainer/state-of-the-repo.md",
    "docs/llms.txt",
]

_SKIP_MARKERS = (
    "shields.io", "img.shields.io",
    "历史快照", "当天的记录", "故意保留", "旧条目",
    "已完成", "已过时", "已放弃", "已完成并前移",
    "snapshot", "historical",
)

_HISTORICAL_SECTION_MARKERS = [
    "## Current baseline",
    "## 2026-08-",
    "## August 2026",
    "## External channel policy",
    "## Standing principles",
    "## Contribution focus",
]

_COUNT_PATTERN = re.compile(
    r"(?<![\w%])(\d{2,5})\+?\s*(?:indexed\s+|verified\s+|managed\s+)?"
    r"(?:failure[-\s]?recovery\s+|failure\s+|debugging\s+)?"
    r"lessons?\b",
    re.IGNORECASE,
)
_DOMAIN_PATTERN = re.compile(
    r"(\d{2,3})\+?\s*(?:domains?|领域|ドメイン)\b",
    re.IGNORECASE,
)


def get_ssot_values() -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/sync_lesson_count.py", "--check"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    values = {}
    for line in result.stdout.splitlines():
        m = re.search(r"lesson count == (\d+)", line)
        if m:
            values["lessons"] = int(m.group(1))
        m = re.search(r"domain count == (\d+)", line)
        if m:
            values["domains"] = int(m.group(1))
    return values


def find_historical_boundaries(content: str) -> set[int]:
    boundaries = set()
    for i, line in enumerate(content.splitlines(), 1):
        for marker in _HISTORICAL_SECTION_MARKERS:
            if line.strip().startswith(marker):
                boundaries.add(i)
    return boundaries


def is_in_historical_section(line_no: int, boundaries: set[int]) -> bool:
    for boundary in sorted(boundaries, reverse=True):
        if line_no >= boundary:
            return True
    return False


def should_skip_line(line_text: str) -> bool:
    return any(marker in line_text for marker in _SKIP_MARKERS)


def scan_file(path: Path, managed_lessons: int, managed_domains: int) -> list[dict]:
    issues = []
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return issues

    rel = path.relative_to(REPO_ROOT)
    boundaries = find_historical_boundaries(content)
    lines = content.splitlines()

    if "maintainer" not in str(rel):
        for pat in [r"自动更新", r"auto[-\s]?updated?\b", r"automatically\s+updated"]:
            for m in re.finditer(pat, content, re.IGNORECASE):
                line_no = content[:m.start()].count("\n") + 1
                issues.append({
                    "file": str(rel), "line": line_no, "severity": "error",
                    "type": "auto_update_claim",
                    "detail": f"claims auto-update: '{m.group()}'",
                })

    for m in _COUNT_PATTERN.finditer(content):
        line_no = content[:m.start()].count("\n") + 1
        line_text = lines[line_no - 1] if line_no <= len(lines) else ""
        if should_skip_line(line_text):
            continue
        claimed = int(m.group(1))
        historical = is_in_historical_section(line_no, boundaries)
        if abs(claimed - managed_lessons) > max(5, managed_lessons * 0.05):
            severity = "warn" if historical else "error"
            issues.append({
                "file": str(rel), "line": line_no, "severity": severity,
                "type": "stale_lesson_count", "claimed": claimed, "actual": managed_lessons,
                "detail": f"claims {claimed} lessons, SSOT says {managed_lessons}"
                         + (" (historical)" if historical else ""),
            })

    for m in _DOMAIN_PATTERN.finditer(content):
        line_no = content[:m.start()].count("\n") + 1
        line_text = lines[line_no - 1] if line_no <= len(lines) else ""
        if should_skip_line(line_text):
            continue
        claimed = int(m.group(1))
        historical = is_in_historical_section(line_no, boundaries)
        if claimed != managed_domains:
            severity = "warn" if historical else "error"
            issues.append({
                "file": str(rel), "line": line_no, "severity": severity,
                "type": "stale_domain_count", "claimed": claimed, "actual": managed_domains,
                "detail": f"claims {claimed} domains, SSOT says {managed_domains}"
                         + (" (historical)" if historical else ""),
            })

    return issues


def main():
    parser = argparse.ArgumentParser(description="Check managed docs for stale numbers")
    parser.add_argument("--check", action="store_true", help="Non-zero exit if errors")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--reverse-test", action="store_true", help="Verify detection works")
    args = parser.parse_args()

    ssot = get_ssot_values()
    managed_lessons = ssot.get("lessons", 0)
    managed_domains = ssot.get("domains", 0)

    if args.reverse_test:
        test_content = "# Test\nWe have {} lessons in our corpus.\n".format(managed_lessons + 100)
        test_path = REPO_ROOT / "_freshness_test_tmp.md"
        test_path.write_text(test_content)
        try:
            issues = scan_file(test_path, managed_lessons, managed_domains)
            errors = [i for i in issues if i["severity"] == "error"]
            if errors:
                print(f"✅ Reverse test passed: detected injected bad number ({managed_lessons + 100})")
                sys.exit(0)
            else:
                print(f"❌ Reverse test FAILED: did not detect injected bad number")
                sys.exit(1)
        finally:
            test_path.unlink()

    all_issues = []
    for fname in MANAGED_FILES:
        fpath = REPO_ROOT / fname
        all_issues.extend(scan_file(fpath, managed_lessons, managed_domains))

    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warn"]

    if args.json:
        print(json.dumps({
            "ssot_lessons": managed_lessons, "ssot_domains": managed_domains,
            "errors": errors, "warnings": warnings, "pass": len(errors) == 0,
        }, indent=2, ensure_ascii=False))
    else:
        if errors:
            print(f"❌ {len(errors)} error(s) contradict SSOT ({managed_lessons} lessons, {managed_domains} domains):")
            for i in errors[:20]:
                print(f"  {i['file']}:{i['line']}: {i['detail']}")
        if warnings:
            print(f"⚠️  {len(warnings)} warning(s) in historical sections:")
            for i in warnings[:10]:
                print(f"  {i['file']}:{i['line']}: {i['detail']}")
        if not errors and not warnings:
            print(f"✅ All managed docs consistent with SSOT ({managed_lessons} lessons, {managed_domains} domains)")

    if args.check and errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
