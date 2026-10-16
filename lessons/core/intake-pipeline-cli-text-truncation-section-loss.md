---
{
  "domain": "python",
  "title": "Intake Pipeline CLI Text Truncation and Section Loss",
  "tags": [
    "python",
    "intake",
    "truncation",
    "pipeline"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "Python录入流水线因硬编码2000字符限制导致长工单尾部段落丢失，移除暴力切片并扩容后解决。",
  "trigger": "2000-char truncation in scripts/intake_pipeline.py cut that issue",
  "verify": "python scripts/audit_intake_kinds.py 退出码为 0"
}
---

Long, multi-section bug reports and intake submissions were losing their trailing explanation and remediation sections due to an early 2,000-character truncation ceiling in `scripts/intake_pipeline.py`.

## Problem

When developers submit comprehensive, multi-point bug reports through the Python intake pipeline, the resulting GitHub issues were truncated mid-sentence around 2,000 characters:
```
The 2,000-char truncation in scripts/intake_pipeline.py cut that issue at items 1-3; trailing sections dropped.
```
Trailing recommendations, reproduction instructions, and plain-language root causes were completely dropped, forcing contributors to manually file fragmented continuation issues.

## Root Cause

Inside `scripts/intake_pipeline.py`, an early sanitization function enforced a hardcoded string slice (`payload = raw_body[:2000]`) prior to formatting markdown wrappers and dispatching API requests. While originally intended as a defensive memory buffer, it failed to scale to complex multi-file tracebacks and structured diagnostic summaries.

## Fix

1. Removed the legacy 2,000-character hard slice from `scripts/intake_pipeline.py` (#2749, #2816).
2. Standardized the pipeline to adopt the system-wide `SUBMITTED_TEXT_CAP = 60000` limit.
3. Implemented a trailing completeness validation pass that checks for unclosed code fences and ensures complete section integrity across intake dispatches.

## Verification

Run the intake audit command to verify that all intake pipeline scripts pass length checks without clipping:

```bash
python scripts/audit_intake_kinds.py
```
Expected output:
```
Auditing intake kinds and payload caps... OK: All intake types valid.
```
