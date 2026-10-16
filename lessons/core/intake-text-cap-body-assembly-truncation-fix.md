---
{
  "domain": "mcp",
  "title": "Intake Text Cap and Body Assembly Truncation Fix",
  "tags": [
    "intake",
    "truncation",
    "mcp",
    "dsh"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "MCP问题录入因硬编码2000字符截断导致长日志丢失，将组装上限扩充至60000字符后彻底解决。",
  "trigger": "intake body assembly cap raised to 60000",
  "verify": "python scripts/audit_intake_kinds.py 退出码为 0"
}
---

Large question intakes submitted via the DSH MCP sidebar were being prematurely truncated to 2,000 characters, dropping vital stack traces and multi-turn debug context before issue creation.

## Problem

When developers submit long diagnostic dumps or complex bug reports exceeding 2,000 characters through the remote MCP intake interface, incoming issue bodies were hard-clipped:
```
Submitted 22,690 chars should arrive in full at GitHub, NOT clipped to 2000.
```
The truncation discarded logs, configuration snippets, and multi-file context, leaving maintainers unable to reproduce the reported errors.

## Root Cause

Early implementations of the intake handler and sidebar fragment assembler applied a conservative 2,000-character ceiling to guard against memory bloat. As the agent architecture evolved to support complete traceback logs and rich markdown payloads, this hardcoded slicing limit remained unadjusted, creating a silent truncation bottleneck during message serialization.

## Fix

1. Raised the intake text cap and body fragment assembly limit from 2,000 to 60,000 characters across the intake ingest pipeline (#2816, #2829).
2. Implemented chunked multi-fragment streaming assembly for incoming payload buffers to prevent buffer overflow.
3. Added automated intake payload length validation ensuring payloads up to 60,000 characters pass end-to-end to GitHub issue creation without data loss.

## Verification

Run the intake kinds audit script to confirm payload handling is healthy across all intake sources:

```bash
python scripts/audit_intake_kinds.py
```
Expected output:
```
Auditing intake kinds and payload caps... OK: All intake types valid.
```
