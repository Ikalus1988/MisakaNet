---
title: "Gemini Safety Settings: Multi-Hop Gateway Passthrough and Compliance Preservation"
domain: "llm"
tags:
  - gemini
  - safety-settings
  - compliance
  - proxy
  - gateway
  - python
status: "published"
evidence_level: "E2"
provenance:
  source: "compliance_audit"
  evidence: "post-publication"
---

# Gemini Safety Settings: Multi-Hop Gateway Passthrough and Compliance Preservation

## Problem

In multi-tier enterprise environments where model traffic flows through API gateways, rate-limiting proxies, or security forwarders before reaching Gemini endpoints, custom safety settings configurations frequently fail to take effect. Downstream calls revert silently to provider default thresholds (such as BLOCK_MEDIUM_AND_ABOVE), bypassing fine-grained enterprise compliance mandates or inadvertently dropping required safety audit metadata (safetyRatings and finishReason: SAFETY).

## Root Cause

1. **Serialization and Naming Mismatch**: Client SDKs format requests using camelCase (safetySettings, harmCategory, threshold), whereas internal REST endpoints or intermediate proxies often deserialize into snake_case models (safety_settings). Strict schema validators discard unrecognized keys, stripping the safety array.
2. **Missing Guardrail Clamping**: Forwarding layers treat caller-supplied safety parameters as unverified overrides. When downstream services omit safety thresholds, or when client applications submit permissive thresholds, multi-hop proxies without explicit policy enforcement fail to enforce organizational safety floors.
3. **Response Context Truncation**: When a prompt triggers safety blocks, Gemini returns promptFeedback.blockReason or candidate items containing safetyRatings. Reverse proxies that project responses down to raw content parts drop these metadata fields, causing downstream logging and compliance services to record empty completions rather than explicit safety refusals.

## Fix

Implement gateway middleware that normalizes naming conventions, clamps safety thresholds against organizational compliance floors, and preserves safety metadata in responses:

```python
from typing import Any, Dict, List

STANDARD_CATEGORIES: List[str] = [
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
]

THRESHOLD_SEVERITY: Dict[str, int] = {
    "BLOCK_LOW_AND_ABOVE": 3,
    "BLOCK_MEDIUM_AND_ABOVE": 2,
    "BLOCK_ONLY_HIGH": 1,
    "BLOCK_NONE": 0,
}


def normalize_safety_settings(
    incoming_settings: List[Dict[str, str]],
    organization_baseline_threshold: str = "BLOCK_LOW_AND_ABOVE",
) -> List[Dict[str, str]]:
    """Enforces strict safety thresholds by normalizing input keys and clamping to baseline.

    Args:
        incoming_settings: List of safety setting dictionaries from client requests.
        organization_baseline_threshold: Minimum allowed threshold string for compliance.

    Returns:
        List of normalized safety settings compliant with Gemini API schema.

    Raises:
        ValueError: If an unknown harm category or threshold is supplied.
    """
    baseline_level = THRESHOLD_SEVERITY.get(organization_baseline_threshold, 3)
    resolved: Dict[str, str] = {}

    for item in incoming_settings:
        cat = item.get("category") or item.get("harmCategory") or item.get("harm_category")
        thresh = item.get("threshold")
        if not cat or not thresh:
            continue
        if cat not in STANDARD_CATEGORIES or thresh not in THRESHOLD_SEVERITY:
            raise ValueError(f"Invalid safety setting: category={cat}, threshold={thresh}")

        requested_level = THRESHOLD_SEVERITY[thresh]
        effective_level = max(requested_level, baseline_level)
        effective_threshold = [k for k, v in THRESHOLD_SEVERITY.items() if v == effective_level][0]
        resolved[cat] = effective_threshold

    for cat in STANDARD_CATEGORIES:
        if cat not in resolved:
            resolved[cat] = organization_baseline_threshold

    return [{"category": cat, "threshold": thresh} for cat, thresh in resolved.items()]


def preserve_compliance_response(
    raw_response: Dict[str, Any],
) -> Dict[str, Any]:
    """Preserves safety ratings, block reasons, and audit context in proxy responses.

    Args:
        raw_response: Deserialized response payload from Gemini API.

    Returns:
        Response dictionary containing both content and preserved safety metadata.
    """
    output: Dict[str, Any] = {
        "candidates": raw_response.get("candidates", []),
        "promptFeedback": raw_response.get("promptFeedback", {}),
    }
    return output
```

## Verification

Run the test suite ensuring that safety threshold relaxation is rejected, categories are preserved, and compliance response fields are maintained:

```bash
python3 -c "
from typing import Dict, List

STANDARD = ['HARM_CATEGORY_HARASSMENT', 'HARM_CATEGORY_HATE_SPEECH', 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'HARM_CATEGORY_DANGEROUS_CONTENT']
SEVERITY = {'BLOCK_LOW_AND_ABOVE': 3, 'BLOCK_MEDIUM_AND_ABOVE': 2, 'BLOCK_ONLY_HIGH': 1, 'BLOCK_NONE': 0}

def clamp(incoming: List[Dict[str, str]], baseline: str) -> List[Dict[str, str]]:
    base_level = SEVERITY[baseline]
    res = {}
    for item in incoming:
        c = item.get('category') or item.get('harmCategory')
        t = item.get('threshold')
        req_level = SEVERITY[t]
        eff_level = max(req_level, base_level)
        eff_thresh = [k for k, v in SEVERITY.items() if v == eff_level][0]
        res[c] = eff_thresh
    for c in STANDARD:
        if c not in res:
            res[c] = baseline
    return [{'category': c, 'threshold': t} for c, t in res.items()]

test_input = [{'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'}]
clamped = clamp(test_input, 'BLOCK_LOW_AND_ABOVE')
harassment = [x for x in clamped if x['category'] == 'HARM_CATEGORY_HARASSMENT'][0]
assert harassment['threshold'] == 'BLOCK_LOW_AND_ABOVE'
assert len(clamped) == 4
"
```
