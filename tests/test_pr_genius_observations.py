import json
from pathlib import Path
import pytest

from scripts.pr_genius_observe import (
    calculate_metrics,
    determine_outcome,
    load_observations,
    record_observation,
    DEFAULT_OBSERVATIONS_PATH,
)


def test_determine_outcome_matrix():
    assert determine_outcome("high_risk", True) == "TP"
    assert determine_outcome("medium_risk", True) == "TP"
    assert determine_outcome("low_risk", False) == "TN"
    assert determine_outcome("low_risk", True) == "FN"
    assert determine_outcome("high_risk", False) == "FP"


def test_default_observations_log_integrity():
    assert DEFAULT_OBSERVATIONS_PATH.exists()
    records = load_observations(DEFAULT_OBSERVATIONS_PATH)
    assert len(records) >= 12

    required_keys = {"id", "pr", "repo", "prediction", "human_conclusion", "outcome", "timestamp"}
    valid_outcomes = {"TP", "TN", "FP", "FN"}

    ids = []
    for r in records:
        for key in required_keys:
            assert key in r, f"Missing key '{key}' in record {r}"
        assert r["outcome"] in valid_outcomes
        assert isinstance(r["id"], int)
        ids.append(r["id"])

    # ID should be strictly monotonically increasing
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_calculate_metrics():
    records = [
        {"outcome": "TP", "useful": True},
        {"outcome": "TP", "useful": True},
        {"outcome": "TN", "useful": False},
        {"outcome": "FP", "useful": False},
        {"outcome": "FN", "useful": False},
    ]
    metrics = calculate_metrics(records)
    assert metrics["total"] == 5
    assert metrics["tp"] == 2
    assert metrics["tn"] == 1
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["accuracy"] == (2 + 1) / 5
    assert metrics["precision"] == 2 / (2 + 1)
    assert metrics["recall"] == 2 / (2 + 1)
    assert metrics["actionable_rate"] == 2 / 5


def test_record_observation_append_only(tmp_path):
    log_file = tmp_path / "observations.jsonl"
    r1 = record_observation(
        pr=100,
        repo="owner/repo",
        prediction="high_risk",
        human_conclusion="Real bug found",
        outcome="TP",
        notes="First record",
        path=log_file,
    )
    assert r1["id"] == 1
    assert r1["outcome"] == "TP"

    r2 = record_observation(
        pr=101,
        repo="owner/repo",
        prediction="low_risk",
        human_conclusion="Clean PR",
        issue_existed=False,
        notes="Second record",
        path=log_file,
    )
    assert r2["id"] == 2
    assert r2["outcome"] == "TN"

    records = load_observations(log_file)
    assert len(records) == 2
    assert records[0]["pr"] == 100
    assert records[1]["pr"] == 101


def test_fp_fn_regression_scenarios():
    """Regression tests for known and edge-case FP/FN patterns."""
    # Pattern 1: Tool claims high risk on docs-only PR without substantive issues -> False Positive
    doc_fp = determine_outcome("high_risk", issue_actually_existed=False)
    assert doc_fp == "FP"

    # Pattern 2: Tool claims low risk, but security vulnerability or subtle lockfile drift existed -> False Negative
    silent_fn = determine_outcome("low_risk", issue_actually_existed=True)
    assert silent_fn == "FN"

    # Pattern 3: Tool flags real DCO / CI failure -> True Positive
    real_tp = determine_outcome("high_risk", issue_actually_existed=True)
    assert real_tp == "TP"

    # Pattern 4: Tool flags clean feature PR as low risk -> True Negative
    clean_tn = determine_outcome("low_risk", issue_actually_existed=False)
    assert clean_tn == "TN"
