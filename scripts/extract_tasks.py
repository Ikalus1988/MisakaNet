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
    """Frontmatter as a dict — JSON (legacy) or YAML, which is what the corpus actually writes.

    This used to match the ``---`` fence and then hand the inside to ``json.loads``. Every lesson
    in this repository writes **YAML** frontmatter (measured 2026-10-14: 516 of 519 files; the 3
    that parse are the JSON ones), so ``json.loads`` raised on every one of them and the function
    returned ``None`` — silently, via the ``except``. The visible consequence was that a
    regeneration labelled **413 of 415** tasks ``domain: "general"`` no matter what the lesson's
    frontmatter said, and collapsed a 9-domain working set to 3.

    Delegated to ``scripts/lesson_gate.parse_frontmatter``, which already handles both shapes
    (and the JSON+provenance legacy quirk) and returns the ``(dict, body)`` pair this needs.
    """
    if str(REPO_ROOT) not in sys.path:      # runnable as `python3 scripts/extract_tasks.py` too
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.lesson_gate import parse_frontmatter  # local import: repo path

    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm or None


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
        # `as_posix()`, not `str()`: on Windows `str()` yields `lessons\en\foo.md`, which then
        # goes into the JSON verbatim. That string does not resolve on any other platform, so the
        # same `tasks/` directory would carry a different `source` shape depending on who last
        # regenerated it. Caught by `test_the_real_corpus_does_collide_and_the_check_can_see_it`,
        # which failed on windows-latest and passed on Linux for exactly this reason.
        "source": path.relative_to(REPO_ROOT).as_posix(),
        "test_cmd": test_cmd,
    }


def duplicate_task_ids(tasks: list[dict]) -> list[tuple[str, list[str]]]:
    """`task_id` values claimed by more than one lesson, with the sources that claim them.

    `task_id` is derived from the filename stem alone (`lesson-<stem>`), so two lessons with the
    same stem in different subdirectories collide. Measured 2026-10-14 on this corpus: **26**
    collisions, every one of them a `lessons/en/<stem>.md` against a `lessons/core/` or
    `lessons/contrib/` lesson of the same stem.

    The corpus has no single rule for whether an `en/` lesson is a translation of the original or
    a lesson in its own right: only **22 of 64** `lessons/en/` files declare `translated_from`
    (and all 22 of those targets exist), while 7 of the 26 colliding `en/` files declare
    nothing. So this reports rather than guesses — see the refusal in `main()`.
    """
    claims: dict[str, list[str]] = {}
    for task in tasks:
        claims.setdefault(task["task_id"], []).append(task["source"])
    return [(tid, srcs) for tid, srcs in claims.items() if len(srcs) > 1]


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

    collisions = duplicate_task_ids(tasks)
    if DRY_RUN:
        print(f"\n{'='*40}")
        print(f"Total lessons: {total}")
        print(f"Extractable:   {extracted}")
        print(f"Skip rate:     {total - extracted}/{total}")
        if collisions:
            print(f"\n{'='*40}")
            print(f"⚠️  {len(collisions)} task_id collision(s) — a write would DROP the earlier "
                  f"lesson(s) silently:")
            for tid, sources in collisions:
                print(f"   {tid}")
                for s in sources:
                    print(f"       <- {s}")
            print("\nResolve these before regenerating: the corpus has no single rule for whether "
                  "an `lessons/en/` file is a translation of an existing lesson or its own. "
                  "Only 22 of 64 declare `translated_from`, so this cannot be inferred.")
        return

    # Refuse to write. The writer below would otherwise overwrite `tasks/<tid>.json` for every
    # collision and lose the earlier lesson without a word — measured 2026-10-14: 26 of them.
    if collisions:
        print("", file=sys.stderr)
        print(f"refusing to write: {len(collisions)} duplicate task_id(s). The writer keys on "
              f"task_id, so each collision silently overwrites the previous lesson.", file=sys.stderr)
        for tid, sources in collisions:
            print(f"  {tid}", file=sys.stderr)
            for s in sources:
                print(f"      <- {s}", file=sys.stderr)
        print("\nDecide per pair whether the en/ variant is a translation of the original (drop "
              "it) or a distinct lesson (make task_id carry the language). Nothing is written "
              "until that is answered.", file=sys.stderr)
        raise SystemExit(1)

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
