#!/usr/bin/env python3
"""
Phase B Benchmark Orchestrator

Runs tasks sequentially in isolated sandboxes, records metrics.
"""
import json
import subprocess
import tempfile
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any, List


def run_task_in_sandbox(task: Dict[str, Any], sandbox_script: Path) -> Dict[str, Any]:
    """Run a single task in the sandbox, return result dict."""
    task_id = task["id"]
    timeout = task.get("timeout", 60)
    
    # Create temp directory for this task
    with tempfile.TemporaryDirectory(prefix=f"task_{task_id}_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Write task fixture if provided
        fixture = task.get("fixture")
        if fixture:
            fixture_path = tmpdir_path / "fixture"
            fixture_path.write_text(fixture)
        
        # Prepare environment
        env = os.environ.copy()
        env["TASK_ID"] = task_id
        env["TASK_FIXTURE"] = str(fixture_path) if fixture else ""
        env["TASK_TIMEOUT"] = str(timeout)
        env["SANDBOX_DIR"] = str(tmpdir_path)
        
        start_time = time.time()
        try:
            # Run sandbox script with task parameters
            result = subprocess.run(
                [str(sandbox_script), task_id, str(timeout)],
                cwd=tmpdir_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout + 5  # Extra buffer for sandbox overhead
            )
            elapsed = time.time() - start_time
            
            success = result.returncode == 0
            
            return {
                "task_id": task_id,
                "success": success,
                "attempts": 1,
                "time_seconds": round(elapsed, 2),
                "cost_usd": 0.0,  # Placeholder for future cost tracking
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return {
                "task_id": task_id,
                "success": False,
                "attempts": 1,
                "time_seconds": round(elapsed, 2),
                "cost_usd": 0.0,
                "stdout": "",
                "stderr": f"Task timed out after {timeout} seconds",
                "returncode": -1
            }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "task_id": task_id,
                "success": False,
                "attempts": 1,
                "time_seconds": round(elapsed, 2),
                "cost_usd": 0.0,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }


def main():
    base_dir = Path(__file__).parent
    tasks_file = base_dir / "tasks.json"
    sandbox_script = base_dir / "sandbox.sh"
    results_file = base_dir / "results.json"
    
    if not tasks_file.exists():
        print(f"Error: {tasks_file} not found", file=sys.stderr)
        sys.exit(1)
    
    if not sandbox_script.exists():
        print(f"Error: {sandbox_script} not found", file=sys.stderr)
        sys.exit(1)
    
    # Make sandbox executable
    sandbox_script.chmod(0o755)
    
    with open(tasks_file) as f:
        tasks = json.load(f)
    
    print(f"Starting Phase B benchmark with {len(tasks)} tasks...")
    
    results = []
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] Running task: {task['id']} - {task.get('name', '')}")
        result = run_task_in_sandbox(task, sandbox_script)
        results.append(result)
        status = "PASS" if result["success"] else "FAIL"
        print(f"  Result: {status} ({result['time_seconds']}s)")
        if not result["success"] and result["stderr"]:
            print(f"  Error: {result['stderr'][:200]}")
    
    # Write results
    output = {
        "benchmark": "phase-b",
        "total_tasks": len(tasks),
        "passed": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "total_time_seconds": round(sum(r["time_seconds"] for r in results), 2),
        "results": results
    }
    
    with open(results_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nBenchmark complete. Results saved to {results_file}")
    print(f"Passed: {output['passed']}/{output['total_tasks']}")
    
    sys.exit(0 if output["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
