#!/usr/bin/env python3
"""Extract problem→fix tasks from lesson corpus.

Reads lessons/*.md, extracts structured benchmarks (tasks/*.json).
Each task captures a real engineering problem + its validated solution,
usable as a benchmark for AI agent evaluation.

Usage:
    python3 scripts/extract_tasks.py              # extract all lessons
    python3 scripts/extract_tasks.py --dry-run     # preview without writing
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "lessons"
TASKS_DIR = REPO_ROOT / "tasks"
DRY_RUN = "--dry-run" in sys.argv

# Sections that describe the problem
PROBLEM_HEADINGS = re.compile(
    r"^##\s+(背景|问题|Root Cause|Problem|Issue|Motivation)",
    re.MULTILINE | re.IGNORECASE,
)
# Sections that describe the solution
SOLUTION_HEADINGS = re.compile(
    r"^##\s+(方案|Solution|Fix|修复|Implementation|Approach)",
    re.MULTILINE | re.IGNORECASE,
)
# Sections that describe verification
VERIFY_HEADINGS = re.compile(
    r"^##\s+(验证|验证方式|Verify|验证结果|Result|Acceptance|效果)",
    re.MULTILINE | re.IGNORECASE,
)


def extract_frontmatter(path: Path) -> dict | None:
    content = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def extract_section(body: str, heading_pattern: re.Pattern, keep_code: bool = False) -> str | None:
    """Extract text under the first matching heading."""
    lines = body.split("\n")
    start = None
    for i, line in enumerate(lines):
        if heading_pattern.match(line):
            start = i + 1
            break
    if start is None:
        return None
    # Collect until next heading of same level
    parts = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        parts.append(line)
    text = "\n".join(parts).strip()
    if not keep_code:
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
    return text[:2000] if text else None


def detect_test_cmd(path: Path, body: str) -> str | None:
    """Detect likely test/verification command from lesson body or filename."""
    # Check for explicit pytest/tox commands in code blocks
    cmd_patterns = [
        r"pytest\s+\S+",
        r"python\s+-m\s+pytest\s+\S+",
        r"tox\s+-e\s+\S+",
        r"pre-commit\s+run\s+\S+",
    ]
    for pat in cmd_patterns:
        m = re.search(pat, body)
        if m:
            return m.group(0)
    return None


def extract_domain_tags(path: Path, fm: dict | None) -> list[str]:
    if fm and "tags" in fm:
        return fm["tags"][:5]  # top 5 tags
    # Fallback: domain from path
    if "contrib" in path.parts:
        return ["contrib"]
    return ["general"]


def lesson_to_task(path: Path) -> dict | None:
    """Convert a lesson markdown file to a benchmark task."""
    content = path.read_text(encoding="utf-8")
    fm = extract_frontmatter(path)

    # Strip frontmatter to get body
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL)

    # Extract sections
    problem = extract_section(body, PROBLEM_HEADINGS)
    solution = extract_section(body, SOLUTION_HEADINGS, keep_code=True)

    # Must have both
    if not problem or not solution:
        return None

    # Title from frontmatter or first line
    title = (fm or {}).get("title", path.stem.replace("-", " ").title())
    domain = (fm or {}).get("domain", "general")
    tags = extract_domain_tags(path, fm)

    task_id = f"lesson-{path.stem.replace('_', '-')[:40]}"

    # Detect test command
    test_cmd = detect_test_cmd(path, body) or ""

    return {
        "task_id": task_id,
        "title": title,
        "domain": domain,
        "tags": tags,
        "problem": problem,
        "solution": solution,
        "source": str(path.relative_to(REPO_ROOT)),
        "test_cmd": test_cmd,
    }


def main():
    paths = sorted(LESSONS_DIR.rglob("*.md"))

    total = 0
    extracted = 0
    tasks = []

    for path in paths:
        if path.name in ("index.md", "README.md"):
            continue
        if "_archive" in str(path):
            continue

        total += 1
        task = lesson_to_task(path)
        if task:
            extracted += 1
            tasks.append(task)
            if DRY_RUN:
                print(f"  ✅ {task['task_id']} — {task['domain']}")

    if DRY_RUN:
        print(f"\n{'='*40}")
        print(f"Total lessons: {total}")
        print(f"Extractable:   {extracted}")
        print(f"Skip rate:     {total - extracted}/{total}")
        return

    # Write tasks
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        tid = task["task_id"]
        path = TASKS_DIR / f"{tid}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)

    # Write index
    index = [{"task_id": t["task_id"], "title": t["title"], "domain": t["domain"],
              "tags": t["tags"], "source": t["source"]} for t in tasks]
    with open(TASKS_DIR / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"✅ {extracted}/{total} lessons extracted to tasks/")
    print(f"   Index: tasks/index.json")


if __name__ == "__main__":
    main()
