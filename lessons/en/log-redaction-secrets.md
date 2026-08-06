---
{
  "title": "Redact secrets from agent logs before they leave the machine",
  "domain": "security",
  "tags": ["secrets", "logging", "redaction", "security", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Redact secrets from agent logs before they leave the machine

## Problem

Earn agents log full HTTP headers, cookies, or env dumps. Tokens leak into chat transcripts and public gists.

## Root Cause

Debug logging prints raw `Authorization`, `Cookie`, and wallet keys. No central redactor.

## Solution

```python
import re

SECRET_RE = re.compile(
    r"(?i)(authorization|cookie|api[_-]?key|token|secret|private[_-]?key)\s*[:=]\s*\S+"
)
BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9._\-]+")

def redact(text: str) -> str:
    text = SECRET_RE.sub(r"\1: [REDACTED]", text)
    text = BEARER_RE.sub("Bearer [REDACTED]", text)
    return text

def log(msg: str) -> None:
    print(redact(msg), flush=True)
```

Never log:

- private keys / seed phrases
- full cookie jars
- raw PAT files

## Verification

```python
assert "[REDACTED]" in redact("Authorization: Bearer abc.def")
assert "abc.def" not in redact("Authorization: Bearer abc.def")
```

## Notes

- Prefer structured logs with explicit allow-listed fields.
- Mode 600 on secret files; never commit them.
