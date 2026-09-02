#!/usr/bin/env python3
"""Validate benchmark result files against the public result schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - requirements.txt includes it
    jsonschema = None
    _JSONSCHEMA_ERROR = exc
else:
    _JSONSCHEMA_ERROR = None


SCHEMA_PATH = Path(__file__).with_name("result.json")


def load_schema() -> dict[str, Any]:
    """Load the checked-in result schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_result(result: dict[str, Any]) -> None:
    """Raise a validation error when ``result`` violates the contract."""
    if jsonschema is None:  # pragma: no cover - exercised on minimal runners
        _validate_without_dependency(result)
        return
    validator = jsonschema.Draft202012Validator(
        load_schema(), format_checker=jsonschema.FormatChecker()
    )
    errors = sorted(validator.iter_errors(result), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:5]
        )
        raise jsonschema.ValidationError(details)


def _validate_without_dependency(result: dict[str, Any]) -> None:
    """Perform the contract's critical checks without an optional package.

    ``jsonschema`` remains the authoritative implementation when installed,
    but the benchmark runner is also used in minimal CI images.  Keeping this
    small fallback prevents a missing developer tool from producing an
    unvalidated result or stopping an otherwise local dry run.
    """
    required = {"meta", "tasks", "summary"}
    missing = required - set(result)
    if missing:
        raise ValueError(f"missing required sections: {sorted(missing)}")
    meta = result["meta"]
    for field in ("run_id", "timestamp", "git_sha", "platform", "node_version"):
        if not isinstance(meta, dict) or not isinstance(meta.get(field), str) or not meta[field]:
            raise ValueError(f"meta.{field} must be a non-empty string")
    tasks = result["tasks"]
    if not isinstance(tasks, list):
        raise ValueError("tasks must be an array")
    allowed_outcomes = {"success", "failure", "timeout", "error"}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"tasks[{index}] must be an object")
        for field in ("task_id", "name", "category", "outcome", "attempts", "duration_ms", "cost_usd", "lessons_used", "error"):
            if field not in task:
                raise ValueError(f"tasks[{index}] missing {field}")
        if task["outcome"] not in allowed_outcomes:
            raise ValueError(f"tasks[{index}].outcome is invalid")
        if not isinstance(task["attempts"], int) or task["attempts"] < 0:
            raise ValueError(f"tasks[{index}].attempts must be a non-negative integer")
        if not isinstance(task["lessons_used"], list):
            raise ValueError(f"tasks[{index}].lessons_used must be an array")
        if task["error"] is not None and not isinstance(task["error"], str):
            raise ValueError(f"tasks[{index}].error must be a string or null")
    summary = result["summary"]
    for field in ("total_tasks", "success_rate", "mean_attempts", "mean_duration", "total_cost"):
        if field not in summary:
            raise ValueError(f"summary missing {field}")
    if summary["total_tasks"] != len(tasks):
        raise ValueError("summary.total_tasks must equal len(tasks)")
    if not 0 <= summary["success_rate"] <= 1:
        raise ValueError("summary.success_rate must be between 0 and 1")


def validate_file(path: Path) -> dict[str, Any]:
    """Read and validate one result file, returning its decoded object."""
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("benchmark result must be a JSON object")
    validate_result(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path, help="result.json to validate")
    args = parser.parse_args()
    try:
        validate_file(args.result)
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"INVALID: {exc}")
        return 1
    print(f"VALID: {args.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
