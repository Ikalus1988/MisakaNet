---
{
  "domain": "security",
  "title": "AgentCap Registry Secret-Safe Validation Failure in Capability Metadata",
  "tags": [
    "agentcap",
    "registry",
    "security",
    "validation"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "能力注册表因描述元数据命中正则导致secret-safe假阳性报错，通过添加边界排除伪阳性即可恢复信任。",
  "trigger": "FAIL secret-safe last refresh validation-failed",
  "verify": "python scripts/audit_dependencies.py 退出码为 0"
}
---

AgentCap capability registry verification reports secret-safe validation failures on capability descriptions and guidance metadata, causing the coordinator to mark the registry as untrusted and fall back to unoptimized local extraction.

## Problem

During automated registry synchronization, read-only capability registries fail the security gate:
```
FAIL: secret-safe; last refresh: validation-failed; Healthy: False
```
While structural schemas and timestamp freshness checks pass cleanly, the secret scanner flags the capability metadata as containing sensitive credentials, blocking registry caching.

## Root Cause

The secret-safe gate scans documentation strings, parameter examples, and guidance descriptions using broad credential matching regular expressions. When tool documentation includes dummy parameter placeholders (such as `Bearer <token>` or mock API keys), the scanner flags these documentation snippets as high-confidence credential leaks, triggering a validation failure.

## Fix

1. Isolate descriptor documentation fields from active credential configuration inputs prior to security scanning.
2. Standardize mock parameter placeholders in capability definitions using neutral sanitization tokens (`<TOKEN_PLACEHOLDER>`).
3. Configure the scanner rule engine to enforce boundary assertions, distinguishing documentation sample snippets from live credentials.

## Verification

Run the capability verification command to confirm that metadata passes the secret-safe check:

```bash
python scripts/audit_dependencies.py
```
Expected output:
```
Capability registry verification: PASSED (secret-safe: clean, Healthy: True)
```
