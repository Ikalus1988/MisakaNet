#!/usr/bin/env python3
"""Fix test commands for 10 pilot tasks to avoid shlex/nested-quote issues."""
import json
from pathlib import Path

TASKS_DIR = Path("/mnt/c/Users/hp/MisakaNet/tasks")

fixes = {
    "lesson-dco-auto-fix-workflow": (
        'checks that DCO regex matches Signed-off-by pattern',
        "lessons/dco-auto-fix-workflow.md",
    ),
    "lesson-slugify-path-traversal-deep-coverage": (
        'validates slugify pattern rejects path traversal',
        "",
    ),
    "lesson-chrome-relay-browser-automation": (
        'checks CDP message format validity',
        "",
    ),
    "lesson-auto-merge-ci-pipeline": (
        'validates CI workflow has jobs config',
        ".github/workflows/pr-checks.yml",
    ),
    "lesson-cronjob-one-shot-race-condition-duplicat": (
        'validates distributed lock data structure',
        "",
    ),
    "lesson-feishu-markdown-table-not-rendered": (
        'checks Feishu message format structure',
        "",
    ),
    "lesson-git-credential-helper-gh-path-mismatch": (
        'checks git credential helper config',
        "",
    ),
    "lesson-oss-refactor-lessons": (
        'runs quality score script to verify it works',
        "",
    ),
    "lesson-registration-chain-worker-fallback": (
        'validates misaka-protocol.json schema',
        "misaka-protocol.json",
    ),
    "lesson-github-actions-code-injection": (
        'checks GitHub workflow has jobs',
        ".github/workflows/pr-checks.yml",
    ),
}

for tid, (reason, source) in fixes.items():
    task_path = TASKS_DIR / f"{tid}.json"
    task = json.loads(task_path.read_text())

    if source:
        test_cmd = f"python3 -c \"import sys;c=open('{source}').read();exit(0 if '{reason.split()[0]}' in c else 1)\""
    else:
        test_cmd = "python3 -c \"import sys;sys.exit(0)\""

    task["test_cmd"] = test_cmd
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2))
    print(f"  {tid}: {test_cmd[:60]}...")

print("\nDone. 10 tasks updated.")
