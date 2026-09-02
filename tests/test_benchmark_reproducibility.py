import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "bench" / "self-healing" / "run_benchmark.py"
DIFF_SCRIPT = SCRIPT.with_name("diff.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_repeats_task_order():
    runner = _load(SCRIPT, "benchmark_runner")
    first = [task_id for task_id, _ in runner._ordered_tasks(seed=42)]
    second = [task_id for task_id, _ in runner._ordered_tasks(seed=42)]
    other = [task_id for task_id, _ in runner._ordered_tasks(seed=7)]
    assert first == second
    assert first != other


def test_history_prunes_old_runs(tmp_path):
    runner = _load(SCRIPT, "benchmark_runner_history")
    for run_id in ("run-a", "run-b", "run-c"):
        result = runner.build_result([], run_id=run_id, seed=1)
        runner.save_history(result, tmp_path, limit=2)
    assert (tmp_path / "run-c" / "results.json").exists()
    assert len(list(tmp_path.glob("*/results.json"))) == 2


def test_diff_flags_success_to_failure_and_slowdown():
    diff = _load(DIFF_SCRIPT, "benchmark_diff")
    before = {
        "run_id": "old",
        "summary": {"success_rate": 1.0},
        "tasks": [{"task_id": "a", "outcome": "success", "duration_ms": 10, "cost_usd": 0}],
    }
    after = {
        "run_id": "new",
        "summary": {"success_rate": 0.0},
        "tasks": [{"task_id": "a", "outcome": "failure", "duration_ms": 20, "cost_usd": 1}],
    }
    report = diff.compare_documents(before, after)
    assert report["changed_outcomes"] == [{"task_id": "a", "before": "success", "after": "failure"}]
    assert {item["kind"] for item in report["regressions"]} == {"outcome", "slower", "more_expensive"}


def test_saved_result_is_json(tmp_path):
    runner = _load(SCRIPT, "benchmark_runner_json")
    path = runner.save_history(runner.build_result([], run_id="json-run", seed=9), tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["seed"] == 9
