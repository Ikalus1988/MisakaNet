---
{
  "title": "Validate JSON agent inputs with a minimal schema check",
  "domain": "python",
  "tags": ["json", "schema", "validation", "python", "agent", "api"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Validate JSON agent inputs with a minimal schema check

## Problem

Agents accept arbitrary JSON from task boards and crash later on missing keys or wrong types. Failures look like random bugs.

## Root Cause

No input gate. Code does `data["url"]` on untrusted payloads.

## Solution

```python
from typing import Any

REQUIRED = {"title": str, "budget_cents": int}

def validate(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("root must be object")
    out = {}
    for key, typ in REQUIRED.items():
        if key not in data:
            raise ValueError(f"missing {key}")
        val = data[key]
        if not isinstance(val, typ):
            raise ValueError(f"{key} must be {typ.__name__}")
        out[key] = val
    return out
```

Call `validate` at the edge (API handler / task claim) before any side effects.

## Verification

```python
validate({"title": "x", "budget_cents": 500})
try:
    validate({"title": "x"})
except ValueError as e:
    assert "missing" in str(e)
```

## Notes

- Prefer jsonschema for complex APIs; keep this pattern for tiny agents.
- Never trust board text as code to exec.
