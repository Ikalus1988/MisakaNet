import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bench.schema.validate import validate_result


def _valid_result():
    return {
        "meta": {
            "run_id": "20260813_120000",
            "timestamp": "2026-08-13T12:00:00+00:00",
            "git_sha": "abc123",
            "platform": "Linux-test",
            "node_version": "v22.0.0",
        },
        "tasks": [{
            "task_id": "dco-signoff",
            "name": "DCO Sign-Off Failure",
            "category": "git",
            "outcome": "success",
            "attempts": 1,
            "duration_ms": 125.5,
            "cost_usd": 0.0,
            "lessons_used": ["dco-auto-fix-workflow"],
            "error": None,
        }],
        "summary": {
            "total_tasks": 1,
            "success_rate": 1.0,
            "mean_attempts": 1.0,
            "mean_duration": 125.5,
            "total_cost": 0.0,
        },
    }


def test_valid_result_is_accepted():
    validate_result(_valid_result())


@pytest.mark.parametrize("field", ["meta", "tasks", "summary"])
def test_required_top_level_sections_are_enforced(field):
    result = _valid_result()
    result.pop(field)
    with pytest.raises(Exception):
        validate_result(result)


def test_invalid_outcome_is_rejected():
    result = _valid_result()
    result["tasks"][0]["outcome"] = "passed"
    with pytest.raises(Exception):
        validate_result(result)


def test_schema_file_is_valid_json():
    schema = json.loads((REPO / "bench/schema/result.json").read_text(encoding="utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
