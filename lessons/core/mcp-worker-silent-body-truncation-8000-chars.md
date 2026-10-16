---
{
  "domain": "cloudflare-worker",
  "title": "MCP Worker Silent Body Truncation at 2000 and 8000 Chars",
  "tags": [
    "mcp",
    "cloudflare-worker",
    "truncation",
    "worker"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "MCP前端Worker存在2000与8000字符的隐蔽硬编码截断，同步扩容至60000并加入截断提示后彻底解决。",
  "trigger": "MCP worker still has a hidden 8000-char cap silently truncates",
  "verify": "python scripts/audit_intake_kinds.py 退出码为 0"
}
---

The Cloudflare Service Worker handling remote MCP intakes silently sheared incoming submission bodies at 2,000 characters in redaction and 8,000 characters during body assembly, dropping critical stack traces without warning markers.

## Problem

Even after upstream pipeline limits were expanded, large bug reports submitted via `misakanet.org/mcp` were clipped before reaching GitHub:
```
Submitted 19,468 chars -> GitHub received 8,765 chars total (~7,850 chars body, ~11,600 chars silently dropped)
```
Crucially, the dropped content carried no `[Truncated at ...]` notice, leading users and maintainers to believe incomplete submissions were sent intact.

## Root Cause

Two legacy buffer caps lingered in `workers/register-proxy-sw.js`:
1. `redactIntake()` applied an unlogged `input.slice(0, 2000)` ceiling before processing markdown blocks.
2. The final body concatenation at line 4224 evaluated:
```javascript
const body = bodyParts.join('\n').slice(0, 8000);
```
Because the slice was applied silently on the joined string, large multi-turn logs and rich stack dumps were truncated with zero telemetry or user-facing alerts.

## Fix

1. Unified the text cap across the JavaScript worker runtime using `SUBMITTED_TEXT_CAP = 60000` (#2816, #2817).
2. Replaced silent slicing with an explicit clipping helper (`clipSubmittedText(text, limit)`) that appends a visible warning banner:
```text
[Warning: Submission body exceeded 60,000 characters and was truncated]
```
3. Updated the intake audit scripts to enforce parity between backend Python parsers and edge Cloudflare Workers.

## Verification

Run the intake audit suite to ensure no hidden truncation limits remain across worker routes:

```bash
python scripts/audit_intake_kinds.py
```
Expected output:
```
Auditing intake kinds and payload caps... OK: All intake types valid.
```
