"""The runway checks for a crash tombstone — the executable form of the v1 contract.

`docs/tombstone-protocol.schema.json` is the contract; this module is the same rules in Python so an
installed wheel can check a payload **without** pulling in `jsonschema` (the package is stdlib-only by
design). `tests/test_tombstone_cli.py` feeds the same payloads through both this validator and the
schema, so the two cannot drift.

The v1 shape is deliberately small: `reason` / `timestamp` / `pid` are required (they are what a draft
needs), everything else is enrichment with a documented limit, and unknown keys are allowed — the
protocol grows additively.
"""
from __future__ import annotations

import re

__all__ = ["REQUIRED", "REASON_PATTERN", "LIMITS", "validate_payload"]

REQUIRED = ("reason", "timestamp", "pid")
REASON_PATTERN = re.compile(
    r"^(uncaught_exception|unhandled_rejection|process_crash|exit_code|killed_by_[A-Z0-9]+)$"
)
TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)
#: name → maximum length, mirroring the schema's `maxLength`.
LIMITS = {
    "errorName": 100,
    "message": 500,
    "stackSnippet": 1000,
    "snippet": 500,
    "signal": 16,
    "host": 100,
    "node_id": 100,
    "tombstone_hash": 128,
}


def validate_payload(data) -> list[str]:
    """Every way this payload breaks the v1 contract; empty means valid."""
    if not isinstance(data, dict):
        return ["tombstone must be a JSON object"]
    problems: list[str] = []
    for field in REQUIRED:
        if field not in data:
            problems.append(f"missing required field: {field}")
    if "schemaVersion" in data and data["schemaVersion"] != 1:
        problems.append(
            f"schemaVersion {data['schemaVersion']!r} is not 1 (v2 is a draft; the reference guard emits 1)"
        )
    reason = data.get("reason")
    if "reason" in data:
        if not isinstance(reason, str) or not REASON_PATTERN.match(reason):
            problems.append(
                f"reason {reason!r} is not one of uncaught_exception / unhandled_rejection / "
                "process_crash / exit_code / killed_by_<SIGNAL>"
            )
    timestamp = data.get("timestamp")
    if "timestamp" in data:
        if not isinstance(timestamp, str) or not TIMESTAMP_PATTERN.match(timestamp):
            problems.append(f"timestamp {timestamp!r} is not ISO 8601 (e.g. 2026-11-09T00:00:00.000Z)")
    pid = data.get("pid")
    if "pid" in data and (not isinstance(pid, int) or isinstance(pid, bool) or pid < 0):
        problems.append(f"pid {pid!r} must be a non-negative integer")
    exit_code = data.get("exit_code")
    if "exit_code" in data and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool) or not 0 <= exit_code <= 255
    ):
        problems.append(f"exit_code {exit_code!r} must be an integer between 0 and 255")
    exitCode = data.get("exitCode")
    if "exitCode" in data and exitCode is not None and (
        not isinstance(exitCode, int) or isinstance(exitCode, bool) or not 0 <= exitCode <= 255
    ):
        problems.append(f"exitCode {exitCode!r} must be null or an integer between 0 and 255")
    for field, limit in LIMITS.items():
        if field not in data:
            continue
        value = data[field]
        if value is None:
            continue
        if not isinstance(value, str):
            problems.append(f"{field} must be a string")
        elif len(value) > limit:
            problems.append(f"{field} is {len(value)} chars; the contract caps it at {limit}")
    return problems
