---
title: "AgentCap secret-safe verification rejects sensitive metadata — how to diagnose without leaking"
domain: development
tags: [agentcap, secret-safe, verification, capability, security, metadata]
status: published
evidence_level: "E0"
summary_plain: "AgentCap 的 secret-safe 检查发现能力描述里有像密钥的内容时会拒绝，只报字段路径不报内容——用 JSON path 定位字段后手动检查并脱敏。"
trigger: "AgentCap secret-safe validation-failed FAIL secret-safe capability verify"
verify: "agentcap verify 2>&1 | grep -q 'secret-safe' && echo 'FAIL' || echo 'PASS: no secret-safe failures'"
provenance: verified
---

## Problem

AgentCap's capability registry verification includes a "secret-safe" check that
scans metadata fields (descriptions, labels, configuration) for patterns resembling
secrets (API keys, tokens, passwords, private keys). When it finds a match, the
verification reports `FAIL: secret-safe` with only the JSON field path (e.g.,
`capabilities[0].description`) — deliberately excluding the flagged content to
avoid leaking sensitive data.

The challenge: how to identify and fix the offending field without being able to
see what triggered the rejection.

## Root Cause

The secret-safe scanner uses pattern matching (regex for common key formats like
`sk-`, `ghp_`, `AKIA`, hex strings of 32+ chars, base64-like strings) against
all text fields in capability metadata. False positives occur when:

1. Documentation contains example API keys or placeholder tokens
2. Hash digests or commit SHAs in descriptions look like secrets
3. Test fixtures contain realistic-looking but fake credentials

The verification intentionally does not echo the flagged content — this is a
security design, not a bug.

## Solution

### Step 1: Identify the affected field

```bash
# Run verification with verbose output
agentcap verify --verbose 2>&1 | grep "secret-safe"
# Output shows JSON paths like: capabilities[2].description
# or: skills[name=deploy].config.endpoint
```

### Step 2: Inspect the field (read-only)

```bash
# Export the capability metadata to a temp file
agentcap export --format json > /tmp/caps.json

# Find the specific field by path
python3 -c "
import json
with open('/tmp/caps.json') as f:
    data = json.load(f)
# Navigate to the path from the error, e.g., capabilities[0].description
desc = data['capabilities'][0]['description']
# Print length and first/last 10 chars (not the full content)
print(f'length={len(desc)}, starts={desc[:10]!r}, ends={desc[-10:]!r}')
"
```

### Step 3: Fix the flagged content

Common fixes:
- Remove example API keys from descriptions
- Replace test tokens with `<REDACTED>` placeholders
- Use environment variable references instead of inline values

```bash
# After fixing, re-verify
agentcap verify 2>&1 | grep "secret-safe"
# Expected: no output (no secret-safe failures)
```

### Step 4: For bulk diagnosis

```bash
# Scan all capability descriptions for common secret patterns
python3 -c "
import json, re
PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',
    r'ghp_[a-zA-Z0-9]{36}',
    r'AKIA[A-Z0-9]{16}',
    r'[a-f0-9]{32,}',  # hex strings
]
with open('/tmp/caps.json') as f:
    data = json.load(f)
for i, cap in enumerate(data.get('capabilities', [])):
    for key, val in cap.items():
        if isinstance(val, str):
            for pat in PATTERNS:
                if re.search(pat, val):
                    print(f'MATCH capabilities[{i}].{key} pattern={pat}')
                    break
"
```

## Verification

```bash
# Check that agentcap verify passes without secret-safe failures
agentcap verify 2>&1 | tee /tmp/verify_out.txt
# Expected: no lines containing "FAIL: secret-safe"

# Confirm: if there ARE failures, they show field paths only (no content)
if grep -q "secret-safe" /tmp/verify_out.txt; then
    # Verify no actual secret values are printed
    python3 -c "
with open('/tmp/verify_out.txt') as f:
    for line in f:
        if 'secret-safe' in line:
            # Should contain a field path, not a secret value
            assert 'capabilities[' in line or 'skills[' in line, f'Unexpected format: {line}'
    print('PASS: secret-safe failures report paths only')
"
fi
```
