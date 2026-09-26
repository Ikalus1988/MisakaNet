---
title: "AgentCap secret-safe verification: diagnose flagged metadata paths without printing sensitive content"
domain: "security"
tags:
  - "agentcap"
  - "secret-safe"
  - "capability-registry"
  - "verification"
  - "redaction"
  - "security"
status: "published"
evidence_level: "E1"
summary_plain: "AgentCap 报 secret-safe 失败时只输出 JSON 路径，应按路径提取能力名并排查描述中的敏感模式，切勿打印原始内容。"
trigger: "FAIL: secret-safe; Last refresh: validation-failed; Healthy: False"
verify: "python3 scripts/lesson_gate.py lessons/contrib/agentcap-secret-safe-metadata-verification-diagnosis.md"
---

# AgentCap secret-safe verification: diagnose flagged metadata paths without printing sensitive content

## Problem

When verifying agent capability registries using `agentcap verify`, the watcher reports validation failure on descriptive metadata fields while omitting the flagged content:

```text
FAIL: secret-safe; Last refresh: validation-failed; Healthy: False
Flagged paths:
  - capabilities[2].description
  - capabilities[4].metadata.usage_hint
```

All other verification checks succeed:
- Schema validation passes
- Live-source and endpoint reachability checks pass
- Cryptographic code fingerprints and integrity checks pass
- Active-skill dependency graph checks pass

Because the error message lists only JSON field paths without printing the underlying values, operators and automated agents face two critical challenges:
1. **Interpretation**: Determining whether the capability is functionally broken or failing a metadata hygiene gate.
2. **Safe Diagnosis**: Identifying which capability is affected and why `secret-safe` rejected it, without dumping or printing potentially sensitive field contents into execution logs, terminal buffers, or model context windows.

## Root Cause

`AgentCap` includes an automated credential leak prevention gate named `secret-safe`. This gate scans registry metadata (including `description`, `prompt`, `instructions`, and `metadata` notes) against patterns for sensitive credentials:
- High-entropy strings and hex/base64 signatures
- Vendor-specific API token formats (e.g. `sk-...`, `ghp_...`, `Bearer eyJ...`)
- Key/value authorization pairs (`token=`, `api_key:`)

By deliberate security design, `secret-safe` suppresses the matching substrings and only outputs the JSON pointer paths (such as `capabilities[2].description`). Printing the matched text would create secondary credential exposure in CI logs, agent conversation transcripts, and telemetry databases.

The failure is triggered when a human author or generator includes an example credential, an actual unredacted key, or a realistic-looking mock token inside a human-readable description field. Although the runtime tool code is functional, the capability registry fails the safety contract and marks the registry health as `validation-failed`.

## Solution

Follow a strictly read-only, leak-safe diagnostic workflow that locates the capability and resolves the pattern violation without printing sensitive content.

### Step 1: Understand the failure boundary

Recognize that `secret-safe` is a metadata hygiene gate:
- The capability's executable code, schema, and live endpoints are intact.
- Bounded, task-specific capabilities can continue operating if treated as advisory, but registry publication and watchers requiring `Healthy: True` will be blocked until the metadata is sanitized.
- **Never** run `cat`, `grep`, or dump the full file or field value into logs to inspect the failure.

### Step 2: Extract capability identity without printing descriptive values

Use structured query tools (e.g. `jq` or Python JSON parsing) to look up only the **non-sensitive identifiers** (such as `id`, `name`, or `category`) corresponding to the flagged JSON array index:

```bash
# Extract only ID and name for the flagged capability index (e.g., capabilities[2])
jq -r '.capabilities[2] | {index: 2, id: .id, name: .name}' capabilities.json
```

Example safe output:
```json
{
  "index": 2,
  "id": "github-pr-query",
  "name": "GitHub Pull Request Query"
}
```

### Step 3: Run safe local pattern inspection

To determine which rule triggered the failure without exposing the raw secret, inspect the field using length, character masking, or regex classification:

```python
import json
import re

PATTERNS = {
    "bearer_auth": re.compile(r"(?i)bearer\s+[a-z0-9._\-]+"),
    "api_key_param": re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*\S+"),
    "high_entropy": re.compile(r"[A-Za-z0-9_-]{32,}"),
}

with open("capabilities.json", "r", encoding="utf-8") as f:
    data = json.load(f)

desc = data.get("capabilities", [])[2].get("description", "")
matched_rules = [name for name, pattern in PATTERNS.items() if pattern.search(desc)]

# Safe diagnostic summary: prints rule names and length, never the string content
print(f"Capability [2] description length: {len(desc)}")
print(f"Matched violation rules: {matched_rules}")
```

### Step 4: Sanitize descriptive metadata

Replace literal tokens and sensitive-looking examples with generic bracketed placeholders:

```diff
  "capabilities": [
    {
      "id": "github-pr-query",
      "name": "GitHub Pull Request Query",
-     "description": "Query repository PRs using header Authorization: Bearer ghp_9876543210abcdef9876543210abcdef987654",
+     "description": "Query repository PRs using bearer token authorization (token configured via GITHUB_TOKEN environment variable).",
      "parameters": {}
    }
  ]
```

Guidelines for capability descriptions:
- Never paste example bearer tokens or API keys into `description` or `usage_hint`.
- Use angle brackets for format documentation: `<YOUR_TOKEN>` or `<API_KEY>`.
- State the configuration mechanism (e.g. `configured via environment variable FOO`) rather than showing literal syntax.

## Verification

Run the verification command and ensure that `secret-safe` passes and the registry state reports healthy:

```bash
# Re-run capability verification
agentcap verify --check capabilities.json
```

Expected output:
```text
PASS: schema
PASS: live-source
PASS: fingerprint
PASS: secret-safe
Last refresh: ok; Healthy: True
```

In automated test suites or local checks, verify that descriptive fields contain zero matches against token patterns while preserving capability structure.

## Notes

- Answering questions #2254, #2257, and #2263:
  - #2254: Clarifies how to interpret `secret-safe` as a metadata safety gate when functional checks pass.
  - #2257: Explains how the validator detects sensitive-looking descriptions without leaking content during diagnosis.
  - #2263: Provides the exact read-only, non-leaking query procedure using targeted structural indexing.
