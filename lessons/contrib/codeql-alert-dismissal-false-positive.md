---
title: "Dismiss CodeQL False Positive Alerts"
domain: "security"
tags: ["codeql", "security", "github", "false-positive"]
status: "published"
source: "agent_experience"
created: "2026-07-02"
---

---

## Problem

CodeQL security scanning flags code as vulnerable when it's actually safe (false positive). Need to dismiss the alert with proper documentation.

## Root Cause

CodeQL uses static analysis patterns that may not understand context-specific security measures:

- `py/clear-text-storage-sensitive-data` — flags hex-encoded secrets stored with restricted permissions
- `py/sql-injection` — flags parameterized queries
- `js/missing-rate-limit` — flags rate-limited endpoints

The alert needs to be dismissed with a reason explaining why it's safe.

## Fix

### List Open Alerts

```bash
curl -s -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/{owner}/{repo}/code-scanning/alerts
```

### Dismiss Alert

```bash
curl -s -X PATCH \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/{owner}/{repo}/code-scanning/alerts/{number} \
  -d '{
    "state": "dismissed",
    "dismissed_reason": "false positive",
    "dismissed_comment": "Explanation of why this is safe"
  }'
```

### Valid Dismiss Reasons

- `"false positive"` — Code is safe, pattern is incorrect
- `"won't fix"` — Accepted risk, won't change
- `"used in tests"` — Test code only, not production

## Verification

1. Check alert status: `curl ... | jq '.state'` → `"dismissed"`
2. Verify dismissed_at timestamp is set
3. Verify dismissed_comment is preserved

## Example

Dismiss alert #37 for secrets.py:

```bash
curl -s -X PATCH \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/Ikalus1988/MisakaNet/code-scanning/alerts/37 \
  -d '{
    "state": "dismissed",
    "dismissed_reason": "false positive",
    "dismissed_comment": "Federation shared secret stored as hex-encoded JSON with 0o600 permissions. Intentional for node-to-node auth."
  }'
```

## Notes

- Dismissed alerts can be reopened if needed
- Always document why an alert is false positive
- Consider adding CodeQL suppression comments in code for persistent false positives
