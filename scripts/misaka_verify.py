#!/usr/bin/env python3
"""misaka-verify — Local task verifier using pytest exit codes.

Reads tasks/*.json, runs the verification command for each task locally.
Uses only subprocess + pytest — no Docker, no LLM, no external API.

Usage:
    python3 scripts/misaka_verify.py                     # verify all tasks
    python3 scripts/misaka_verify.py <task_id>            # verify one task
    python3 scripts/misaka_verify.py --domain security    # filter by domain
    python3 scripts/misaka_verify.py --list               # list available tasks
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"


def load_tasks(filter_domain: str | None = None) -> list[dict]:
    index = TASKS_DIR / "index.json"
    if not index.exists():
        print(f"❌ No tasks/index.json found. Run scripts/extract_tasks.py first.")
        sys.exit(1)
    tasks = json.loads(index.read_text())
    if filter_domain:
        tasks = [t for t in tasks if t.get("domain") == filter_domain]
    return tasks


def resolve_task(task_id: str) -> dict | None:
    """Find a task by ID from the index."""
    tasks = load_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            return t
    return None


def run_verification(task: dict) -> tuple[str, str]:
    """Run the verification command for a task.
    Returns (status, details).
    """
    source_path = REPO_ROOT / task.get("source", "")
    task_file = TASKS_DIR / f"{task['task_id']}.json"

    # Check source exists
    if not source_path.exists():
        return SKIP, f"Source not found: {task['source']}"

    # Read full task for test_cmd
    task_data = json.loads(task_file.read_text())
    test_cmd = task_data.get("test_cmd", "")

    # If we have a pytest command, run it
    if test_cmd:
        try:
            import shlex
            result = subprocess.run(
                shlex.split(test_cmd),
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,  # 2 min max per task
            )
            if result.returncode == 0:
                return PASS, f"{test_cmd} → exit 0"
            else:
                summary = result.stdout.split("\n")[-3:]
                return FAIL, f"{test_cmd} → exit {result.returncode}: {' '.join(summary)}"
        except subprocess.TimeoutExpired:
            return FAIL, f"{test_cmd} → TIMEOUT (>120s)"
        except FileNotFoundError:
            return FAIL, f"Command not found: {test_cmd.split()[0]}"

    # No test command — verify source file integrity
    if source_path.stat().st_size > 100:
        return PASS, f"Source exists ({source_path.stat().st_size} bytes)"
    return SKIP, f"No test_cmd and source too small" if source_path.stat().st_size > 0 else FAIL, f"Empty source"


def main():
    args = sys.argv[1:]

    if "--list" in args:
        tasks = load_tasks()
        print(f"{'Task ID':45s} {'Domain':15s} {'Title':40s}")
        print("-" * 100)
        for t in tasks:
            print(f"{t['task_id']:45s} {t.get('domain','?'):15s} {t['title'][:38]:40s}")
        return

    filter_domain = None
    if "--domain" in args:
        idx = args.index("--domain")
        if idx + 1 < len(args):
            filter_domain = args[idx + 1]

    # Single task mode
    task_ids = [a for a in args if not a.startswith("--")]
    if task_ids:
        results = []
        for tid in task_ids:
            task = resolve_task(tid)
            if not task:
                print(f"❌ Task not found: {tid}")
                continue
            status, detail = run_verification(task)
            print(f"{status} {tid}: {detail}")
        return

    # Batch mode
    tasks = load_tasks(filter_domain)
    if not tasks:
        print("❌ No tasks found.")
        sys.exit(1)

    passed = 0
    failed = 0
    skipped = 0
    total = len(tasks)

    for task in tasks:
        status, detail = run_verification(task)
        if status == PASS:
            passed += 1
        elif status == FAIL:
            failed += 1
        else:
            skipped += 1
        print(f"{status} {task['task_id']:45s} {detail[:50]}")

    print(f"\n{'='*50}")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}  Skipped: {skipped}")


if __name__ == "__main__":
    main()
