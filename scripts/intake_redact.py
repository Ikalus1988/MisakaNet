#!/usr/bin/env python3
"""Intake payload redaction — strip secrets before persistence.

Redacts: API keys, GitHub tokens, Slack tokens, private keys,
passwords, credit cards, and environment variable dumps.

Patterns are loaded from workers/lib/redact-patterns.json (single source
of truth shared with the JS implementation).

Usage:
    from scripts.intake_redact import redact_payload, redact_text
    safe = redact_text(raw_message)
    safe_record = redact_payload(raw_record)
"""
import json
import re
from pathlib import Path
from typing import Any

# ── Load shared redaction patterns ──

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PATTERN_FILE = _REPO_ROOT / "workers" / "lib" / "redact-patterns.json"

def _load_patterns() -> list[tuple[re.Pattern, str]]:
    """Load patterns from shared JSON file."""
    data = json.loads(_PATTERN_FILE.read_text(encoding="utf-8"))
    flags_map = {"i": re.IGNORECASE, "g": 0, "gi": re.IGNORECASE}
    result = []
    for p in data:
        flags = flags_map.get(p.get("flags", "g"), 0)
        result.append((re.compile(p["pattern"], flags), p["replacement"]))
    return result

REDACT_PATTERNS: list[tuple[re.Pattern, str]] = _load_patterns()

# Patterns for detecting env-dump payloads
ENV_DUMP_PATTERNS = [
    re.compile(r"^(?:export\s+)?[A-Z_]{3,}=.+", re.MULTILINE),
    re.compile(r"\b(?:AWS_SECRET|DATABASE_URL|MONGO_URI|REDIS_URL|PRIVATE_KEY)\b", re.IGNORECASE),
]


def redact_text(text: str, max_length: int = 2000) -> str:
    """Redact secrets from a text string. Truncates to max_length."""
    if not text:
        return ""
    result = str(text)[:max_length]
    for pattern, replacement in REDACT_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def is_env_dump(text: str) -> bool:
    """Detect if text looks like an environment variable dump."""
    if not text:
        return False
    matches = sum(1 for p in ENV_DUMP_PATTERNS if p.search(text))
    return matches >= 2


def redact_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets from an intake record. Returns a new dict."""
    if not isinstance(record, dict):
        return {}

    safe = dict(record)

    # Check env dump BEFORE redaction (redaction may alter env var names)
    if isinstance(safe.get("message"), str) and is_env_dump(safe["message"]):
        safe["_env_dump_detected"] = True

    # Redact string fields that may contain secrets
    for field in ("message", "context", "description", "error", "traceback",
                   "title", "problem", "root_cause", "fix", "verification"):
        if field in safe and isinstance(safe[field], str):
            safe[field] = redact_text(safe[field])

    # Redact nested context object
    if "context" in safe and isinstance(safe["context"], dict):
        ctx = {}
        for k, v in safe["context"].items():
            if isinstance(v, str):
                ctx[k] = redact_text(v, max_length=500)
            else:
                ctx[k] = v
        safe["context"] = ctx

    # If env dump was detected, replace message with marker
    if safe.get("_env_dump_detected"):
        safe["message"] = "[REDACTED:env_dump]"

    return safe


def redaction_summary(record: dict[str, Any], safe: dict[str, Any]) -> dict[str, int]:
    """Count redactions applied by comparing original and safe records."""
    summary = {"total": 0}
    for field in ("message", "context", "description", "error", "traceback"):
        orig = str(record.get(field, ""))
        redacted = str(safe.get(field, ""))
        if orig == redacted:
            continue
        # Count [REDACTED:...] markers in the redacted text
        count = redacted.count("[REDACTED:")
        if count:
            summary[field] = count
            summary["total"] += count
        elif safe.get("_env_dump_detected") and field == "message":
            # env dump was replaced entirely
            summary[field] = 1
            summary["total"] += 1
    if safe.get("_env_dump_detected") and "message" not in summary:
        summary["env_dump"] = 1
        summary["total"] += 1
    return summary
