---
{
  "provenance": {"source": "intake", "issue": "#2769", "related": ["#2833", "#2834"]},
  "domain": "testing",
  "title": "Intake Stress Testing for 20K to 60K Payload Boundaries",
  "tags": [
    "testing",
    "intake",
    "stress-test",
    "truncation"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "通过2万至6万字符高负载压力测试用例验证全链路传输，确保大体积工单在边缘与后端间零截断。",
  "trigger": "20K truncation test deliberate stress test body assembly cap",
  "verify": "python scripts/audit_intake_kinds.py 退出码为 0"
}
---

Automated stress testing of intake payloads between 20,000 and 60,000 characters requires end-to-end length verification across edge Cloudflare Workers and backend API adapters to prevent silent payload loss.

## Problem

When verifying whether truncation fixes hold under production conditions, developers running high-volume stress tests (such as deliberate 20,000+ character submissions) encountered conflicting test results:
```
Submitted 22,690 chars should arrive in full at GitHub, NOT clipped to 2000.
```
While small mock inputs (&lt;2,000 characters) passed all unit tests, realistic debug dumps containing dense stack traces and configuration blocks were intermittently clipped by intermediate proxies.

## Root Cause

Test suites historically evaluated synthetic single-line strings that never exercised memory buffers or multi-chunk streaming handlers. In production, edge workers (such as Cloudflare Service Workers) and backend intake scripts (`scripts/intake_pipeline.py`) enforced differing buffer limits. Without synchronized end-to-end stress tests, multi-stage pipelines passed localized unit tests while failing live high-volume transmissions.

## Fix

1. Created dedicated stress test fixtures with multi-section payloads scaled to 20,000 and 60,000 characters (#2769, #2833).
2. Embedded self-referential token markers at the head, midpoint, and tail of stress payloads to verify zero loss across pipeline boundaries.
3. Asserted that submissions below the `SUBMITTED_TEXT_CAP = 60000` ceiling land on GitHub with 100% byte fidelity and zero truncation notice banners.

## Verification

Run the intake audit script to verify that payload validation logic correctly enforces 60,000-character capacity across all sources:

```bash
python scripts/audit_intake_kinds.py
```
Expected output:
```
Auditing intake kinds and payload caps... OK: All intake types valid.
```
