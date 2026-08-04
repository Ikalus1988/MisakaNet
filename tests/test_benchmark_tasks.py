#!/usr/bin/env python3
"""Tests for benchmark task catalog schema and references."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from misakanet.search.engine import REPO

TASKS_FILE = REPO / "data" / "benchmark_tasks.json"
REQUIRED_FIELDS = {"task_id", "title", "failure", "expected_action", "lesson_ref", "verifier_type"}
VALID_VERIFIERS = {"command_exit", "http_status", "file_content", "log_pattern", "process_alive"}


def _load_tasks():
    with open(TASKS_FILE, encoding="utf-8") as f:
        return json.load(f)


class TestBenchmarkTasks:
    def test_file_exists(self):
        assert TASKS_FILE.exists(), f"{TASKS_FILE} not found"

    def test_minimum_count(self):
        tasks = _load_tasks()
        assert len(tasks) >= 10, f"Expected >= 10 tasks, got {len(tasks)}"

    def test_unique_ids(self):
        tasks = _load_tasks()
        ids = [t["task_id"] for t in tasks]
        assert len(ids) == len(set(ids)), "Duplicate task_id found"

    def test_schema_fields(self):
        tasks = _load_tasks()
        for task in tasks:
            missing = REQUIRED_FIELDS - set(task.keys())
            assert not missing, f"Task {task.get('task_id')} missing fields: {missing}"

    def test_verifier_type_valid(self):
        tasks = _load_tasks()
        for task in tasks:
            vtype = task.get("verifier_type")
            assert vtype in VALID_VERIFIERS, (
                f"Invalid verifier_type '{vtype}' in {task.get('task_id')}"
            )

    def test_no_random_simulated_results(self):
        tasks = _load_tasks()
        for task in tasks:
            assert "random" not in task["failure"].lower()
            assert "simulated" not in task["failure"].lower()
            assert "fake" not in task["failure"].lower()
            assert "random" not in task["expected_action"].lower()

    def test_lesson_refs_exist(self):
        tasks = _load_tasks()
        for task in tasks:
            ref = Path(task["lesson_ref"])
            assert ref.exists(), f"lesson_ref not found: {ref}"

    def test_expected_action_present(self):
        tasks = _load_tasks()
        for task in tasks:
            action = task.get("expected_action", "")
            assert len(action) >= 10, (
                f"expected_action too short in {task.get('task_id')}"
            )
