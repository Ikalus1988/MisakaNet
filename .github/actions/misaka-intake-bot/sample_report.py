#!/usr/bin/env python3
"""Compose one NDJSON sample-report line from an intake-bot JSON result.

Used by .github/actions/misaka-intake-bot (composite action) so external
pilots can accumulate per-decision samples into a >=N-sample report
(see docs/agents/failure-feedback-flywheel-research.md §4 for the schema).

Usage:  sample_report.py '<intake-bot json result>'
Output: single-line JSON on stdout (empty decision -> still one line).
"""
import json
import os
import sys


def main() -> int:
    raw = sys.argv[1] if len(sys.argv) > 1 else "{}"
    try:
        res = json.loads(raw)
    except Exception:
        res = {}
    row = {
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "decision": res.get("decision", "unknown"),
        "fingerprint": res.get("fingerprint", ""),
    }
    lesson = res.get("lesson") or {}
    if lesson:
        row["lesson_id"] = lesson.get("id")
        row["sim"] = lesson.get("sim")
        row["lesson_url"] = lesson.get("url")
    if res.get("receipt"):
        row["receipt"] = str(res["receipt"])[:200]
    if res.get("reason"):
        row["reason"] = str(res["reason"])[:200]
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
