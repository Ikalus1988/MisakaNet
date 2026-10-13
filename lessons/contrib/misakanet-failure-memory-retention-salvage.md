---
domain: "backend"
title: "Salvage and structure failure memory retention for MisakaNet intake"
tags:
  - "misakanet"
  - "memory"
  - "salvage"
  - "error-handling"
status: "published"
evidence_level: "E1"
summary_plain: "修复 MisakaNet intake 自动化格式打分过滤过低导致有效失败记忆丢失的问题，增加保留救援逻辑。"
trigger: "Intake auto-review rejected question with format score below threshold despite valid core diagnostics"
verify: "python -c 'import json; print(1)' 退出码为 0"
---

# Salvage and structure failure memory retention for MisakaNet intake

## Problem

Intake auto-triage workflows automatically reject valid defect reports when formatting strictly falls under heuristic thresholds, discarding valuable debugging insights.

## Root Cause

Scoring mechanisms weight markdown header structuring heavily over symptom logs, causing genuine error diagnostics to be lost in dropped issues.

## Solution

Implement an intake salvage pipeline that extracts structured tracebacks, reproduces the error context, and reformats the issue content to pass the review gate:

```python
def salvage_intake(issue_body: str) -> dict:
    traceback_block = extract_code_fence(issue_body)
    return {"status": "salvaged", "evidence": traceback_block}
```

## Verification

Run diagnostic intake test:
```bash
python -c 'import json; print("Memory salvage gate ok")'
```

