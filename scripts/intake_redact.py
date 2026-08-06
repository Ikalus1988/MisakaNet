#!/usr/bin/env python3
"""Intake payload redaction — strip secrets before persistence.

Redacts: API keys, GitHub tokens, Slack tokens, private keys,
passwords, credit cards, and environment variable dumps.

Usage:
    from scripts.intake_redact import redact_payload, redact_text
    safe = redact_text(raw_message)
    safe_record = redact_payload(raw_record)
"""
import re
from typing import Any

# ── Redaction patterns (order matters: longest match first) ──

REDACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Private keys (PEM blocks) — must come first (large multiline match)
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END(?: RSA | EC | OPENSSH )?PRIVATE KEY-----", re.IGNORECASE),
     "[REDACTED:private_key]"),
    # GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_, github_pat_) — before generic key-value
    (re.compile(r"(?:ghp|gho|ghu|ghs|ghr|github_pat)_[a-zA-Z0-9]{10,}"),
     "[REDACTED:github_token]"),
    # Slack tokens (xoxb-, xoxp-, xoxa-, xoxr-)
    (re.compile(r"xox[bpras]-[a-zA-Z0-9\-]{10,}"),
     "[REDACTED:slack_token]"),
    # AWS access key — before generic key-value
    (re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}"),
     "[REDACTED:aws_key]"),
    # Generic API keys (sk-*, pk-*, rk-*, ak-* with 10+ chars)
    (re.compile(r"(?:sk|pk|rk|ak)[_-][a-zA-Z0-9]{10,}"),
     "[REDACTED:api_key]"),
    # Bearer token in headers — before generic key-value
    (re.compile(r"(?:Bearer|Authorization)\s+[a-zA-Z0-9\-._~+/]+=*", re.IGNORECASE),
     "[REDACTED:bearer_token]"),
    # key=value or key: value secrets (password, passwd, secret, token, api_key, apikey, database_url)
    (re.compile(r"(?:password|passwd|secret|token|api[_-]?key|apikey|database[_-]?url)\s*[:=]\s*\S+", re.IGNORECASE),
     "[REDACTED:credential]"),
    # Credentials in URLs (user:pass@host)
    (re.compile(r"://[^:]+:[^@]+@[^\s]+"),
     "://[REDACTED:url_credential]@host"),
    # Credit card numbers (13-19 digits, with optional spaces/dashes)
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
     "[REDACTED:card_number]"),
]

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
    for field in ("message", "context", "description", "error", "traceback"):
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
