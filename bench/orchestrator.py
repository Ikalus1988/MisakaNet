"""Benchmark orchestrator with deterministic seeds and run comparison."""

import argparse
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_benchmark(seed: int, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run benchmark with given seed. Returns results dict."""
    # Set deterministic seeds
    random.seed(seed)
    # If numpy is used elsewhere, seed it too
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    
    # Simulate benchmark tasks (replace with actual benchmark logic)
    tasks = config.get("tasks", ["task1", "task2", "task3"])
    results = {
        "run_id": str(uuid.uuid4())[:8],
        "seed": seed,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "config": config,
        "tasks": {},
        "summary": {
            "total": len(tasks),
            "passed": 0,
            "failed": 0,
            "total_latency_ms": 0,
            "total_cost_usd": 0.0
        }
    }
    
    for task in tasks:
        # Deterministic simulation based on seed + task name
        task_seed = hash((seed, task)) % (2**32)
        random.seed(task_seed)
        
        success = random.random() > 0.2  # 80% success rate
        latency = random.randint(100, 5000)
        cost = round(random.uniform(0.001, 0.1), 4)
        
        results["tasks"][task] = {
            "success": success,
            "latency_ms": latency,
            "cost_usd": cost,
            "error": None if success else "Simulated failure"
        }
        
        if success:
            results["summary"]["passed"] += 1
        else:
            results["summary"]["failed"] += 1
        results["summary"]["total_latency_ms"] += latency
        results["summary"]["total_cost_usd"] += cost
    
    results["summary"]["total_cost_usd"] = round(results["summary"]["total_cost_usd"], 4)
    return results


def save_results(results: Dict[str, Any], history_dir: Path) -> Path:
    """Save results to history directory."""
    history_dir.mkdir(parents=True, exist_ok=True)
    
    run_id = results["run_id"]
    filepath = history_dir / f"{run_id}.json"
    
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
    
    # Also save as latest.json for easy access
    latest_path = history_dir / "latest.json"
    with open(latest_path, "w") as f:
        json.dump(results, f, indent=2)
    
    # Maintain index of runs
    index_path = history_dir / "index.json"
    index = []
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    
    index.insert(0, {
        "run_id": run_id,
        "seed": results["seed"],
        "timestamp": results["timestamp"],
        "passed": results["summary"]["passed"],
        "failed": results["summary"]["failed"]
    })
    
    # Keep last 50 runs
    index = index[:50]
    
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    
    return filepath


def load_results(run_id: str, history_dir: Path) -> Optional[Dict[str, Any]]:
    """Load results for a given run_id."""
    filepath = history_dir / f"{run_id}.json"
    if not filepath.exists():
        # Try latest.json if run_id is 'latest'
        if run_id == "latest":
            filepath = history_dir / "latest.json"
        else:
            return None
    
    with open(filepath) as f:
        return json.load(f)


def list_runs(history_dir: Path) -> List[Dict[str, Any]]:
    """List recent runs from index."""
    index_path = history_dir / "index.json"
    if not index_path.exists():
        return []
    with open(index_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="MisakaNet Benchmark Orchestrator")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for deterministic runs")
    parser.add_argument("--compare", type=str, default=None,
                        help="Compare current run with run_id (or 'latest')")
    parser.add_argument("--config", type=str, default="bench/config.json",
                        help="Path to benchmark config")
    parser.add_argument("--history-dir", type=str, default="bench/history",
                        help="Directory to store run history")
    parser.add_argument("--list-runs", action="store_true",
                        help="List recent runs and exit")
    
    args = parser.parse_args()
    
    history_dir = Path(args.history_dir)
    
    if args.list_runs:
        runs = list_runs(history_dir)
        if not runs:
            print("No runs found.")
            return 0
        print(f"{'Run ID':<10} {'Seed':<10} {'Timestamp':<25} {'Passed':<8} {'Failed':<8}")
        print("-" * 70)
        for run in runs:
            print(f"{run['run_id']:<10} {run['seed']:<10} {run['timestamp']:<25} {run['passed']:<8} {run['failed']:<8}")
        return 0
    
    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {"tasks": ["search_test", "retrieval_test", "generation_test"]}
    
    # Determine seed
    seed = args.seed if args.seed is not None else int(time.time() * 1000) % (2**32)
    
    # Run benchmark
    print(f"Running benchmark with seed={seed}")
    results = run_benchmark(seed, config)
    
    # Save results
    saved_path = save_results(results, history_dir)
    print(f"Results saved to {saved_path}")
    print(f"Run ID: {results['run_id']}")
    print(f"Passed: {results['summary']['passed']}, Failed: {results['summary']['failed']}")
    
    # Compare if requested
    if args.compare:
        print(f"\nComparing with run: {args.compare}")
        # Import and run diff
        sys.path.insert(0, str(Path(__file__).parent / "scripts"))
        from diff import compare_runs
        
        baseline = load_results(args.compare, history_dir)
        if not baseline:
            print(f"Error: Baseline run '{args.compare}' not found")
            return 1
        
        diff_result = compare_runs(baseline, results)
        print_diff(diff_result)
    
    return 0


def print_diff(diff: Dict[str, Any]):
    """Print formatted diff output."""
    print("\n" + "=" * 60)
    print("DIFF REPORT")
    print("=" * 60)
    print(f"Baseline: {diff['baseline_run_id']} (seed={diff['baseline_seed']})")
    print(f"Current:  {diff['current_run_id']} (seed={diff['current_seed']})")
    print()
    
    if diff["regressions"]:
        print("🔴 REGRESSIONS:")
        for reg in diff["regressions"]:
            print(f"  - {reg}")
    else:
        print("✅ No regressions detected")
    
    if diff["improvements"]:
        print("\n🟢 IMPROVEMENTS:")
        for imp in diff["improvements"]:
            print(f"  - {imp}")
    
    if diff["task_changes"]:
        print("\n📋 TASK OUTCOME CHANGES:")
        for change in diff["task_changes"]:
            status = "✅→❌" if change["baseline_success"] and not change["current_success"] else "❌→✅"
            print(f"  {status} {change['task']}: {change['baseline_error']} -> {change['current_error']}")
    
    if diff["metric_changes"]:
        print("\n📊 METRIC CHANGES:")
        for metric, change in diff["metric_changes"].items():
            direction = "↑" if change["delta"] > 0 else "↓"
            print(f"  {metric}: {change['baseline']} -> {change['current']} ({direction}{abs(change['delta']):.2f})")
    
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
