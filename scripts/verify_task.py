#!/usr/bin/env python3
"""Enhanced task verifier with optional code execution.

Upgraded from file-existence-only check to real pytest execution.
Uses the task's test_cmd field to run verification.

Usage:
    python3 scripts/verify_task.py <task_id>              # basic check
    python3 scripts/verify_task.py <task_id> --execute    # run test_cmd
    python3 scripts/verify_task.py <task_id> --sandbox    # run in subprocess
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def check_basic(task: dict, source_path: Path) -> dict:
    """Basic checks: file existence, problem/solution presence."""
    checks = {"source_exists": False, "has_problem": False, "has_solution": False}
    passed = 0
    total = 3

    if source_path.exists():
        checks["source_exists"] = True
        passed += 1

    if task.get("problem"):
        checks["has_problem"] = True
        passed += 1

    if task.get("solution"):
        checks["has_solution"] = True
        passed += 1

    return {"passed": passed, "total": total, "checks": checks}


def check_execution(task: dict) -> dict:
    """Execute the task's test_cmd and return results."""
    test_cmd = task.get("test_cmd", "")
    if not test_cmd:
        return {"passed": 0, "total": 0, "checks": {}, "note": "No test_cmd defined"}

    result = {"passed": 0, "total": 1, "checks": {"test_cmd_executed": False}}

    try:
        proc = subprocess.run(
            test_cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(REPO),
            timeout=60,
        )
        result["checks"]["test_cmd_executed"] = True
        result["checks"]["exit_code"] = proc.returncode
        result["checks"]["stdout_tail"] = proc.stdout.strip()[-500:] if proc.stdout else ""
        result["checks"]["stderr_tail"] = proc.stderr.strip()[-500:] if proc.stderr else ""
        if proc.returncode == 0:
            result["passed"] = 1
        else:
            result["checks"]["failure_reason"] = f"Exit code {proc.returncode}"
    except subprocess.TimeoutExpired:
        result["checks"]["failure_reason"] = "Timeout (60s)"
    except FileNotFoundError as e:
        result["checks"]["failure_reason"] = f"Command not found: {e}"
    except Exception as e:
        result["checks"]["failure_reason"] = str(e)

    return result


def run_pytest_on_agent_output(task: dict, agent_code: str = "") -> dict:
    """Write agent's fix code to a temp file and run pytest against it.
    
    For tasks that include a reference solution file, this writes the agent's
    proposed fix and runs the associated test suite.
    """
    result = {"passed": 0, "total": 1, "checks": {}}
    
    source = task.get("source", "")
    if not source or not agent_code:
        return {"passed": 0, "total": 0, "checks": {}, "note": "No source file or agent code"}

    # Write agent code to a temp location
    tmpdir = tempfile.mkdtemp(prefix="misakanet_verify_")
    fix_path = Path(tmpdir) / Path(source).name
    fix_path.write_text(agent_code, encoding="utf-8")

    # Look for a corresponding test file
    source_stem = Path(source).stem
    test_candidates = [
        REPO / "tests" / f"test_{source_stem}.py",
        REPO / "tests" / f"test_{source_stem}_fix.py",
    ]
    
    test_file = None
    for candidate in test_candidates:
        if candidate.exists():
            test_file = candidate
            break

    if test_file:
        try:
            proc = subprocess.run(
                ["python3", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                capture_output=True, text=True, cwd=str(REPO), timeout=120,
                env={**os.environ, "MISAKANET_FIX_PATH": str(fix_path)},
            )
            result["checks"]["pytest_stdout"] = proc.stdout.strip()[-1000:]
            result["checks"]["pytest_stderr"] = proc.stderr.strip()[-500:]
            if proc.returncode == 0:
                result["passed"] = 1
                result["checks"]["pytest_outcome"] = "PASS"
            else:
                result["checks"]["pytest_outcome"] = "FAIL"
                result["checks"]["failure_reason"] = f"pytest exit {proc.returncode}"
        except Exception as e:
            result["checks"]["failure_reason"] = str(e)
    else:
        result["checks"]["note"] = "No test file found for this task"

    return result


def main():
    task_id = sys.argv[1] if len(sys.argv) > 1 else ""
    execute = "--execute" in sys.argv
    sandbox = "--sandbox" in sys.argv

    if not task_id:
        print("Usage: python3 scripts/verify_task.py <task_id> [--execute] [--sandbox]")
        sys.exit(1)

    task_file = REPO / "tasks" / f"{task_id}.json"
    if not task_file.exists():
        # Try draft tasks
        draft_file = REPO / "lessons" / "drafts" / f"{task_id}.json"
        if draft_file.exists():
            task_file = draft_file
        else:
            print(f"Task not found: {task_id}")
            sys.exit(1)

    task = json.loads(task_file.read_text())
    source = task.get("source", "")
    source_path = REPO / source if source else Path("/dev/null")

    # Phase 1: Basic checks
    basic = check_basic(task, source_path)
    
    print(f"  {task.get('title', task_id)[:50]}")
    print(f"  source: {source} "
          f"({source_path.stat().st_size if source_path.exists() else 0} bytes)")
    print(f"  Phase 1 (basic): {basic['passed']}/{basic['total']} checks passed")
    for k, v in basic["checks"].items():
        icon = "ok" if v else "FAIL"
        print(f"    {icon}: {k}")

    # Phase 2: Execution (if --execute)
    if execute:
        exec_result = check_execution(task)
        if exec_result["total"] > 0:
            print(f"  Phase 2 (execute): {exec_result['passed']}/{exec_result['total']}")
            for k, v in exec_result["checks"].items():
                if k == "stderr_tail" and v:
                    print(f"    stderr: {v[:200]}")
                elif k == "failure_reason" and v:
                    print(f"    FAIL: {v}")
                else:
                    print(f"    {k}: {v}")
        elif exec_result.get("note"):
            print(f"  Phase 2: {exec_result['note']}")

    # Overall verdict
    total_passed = basic["passed"] + (exec_result.get("passed", 0) if execute else 0)
    total_checks = basic["total"] + (exec_result.get("total", 0) if execute else 0)
    
    if total_passed == total_checks:
        print(f"  OK: {total_passed}/{total_checks} checks passed")
        sys.exit(0)
    else:
        print(f"  FAIL: {total_passed}/{total_checks} checks passed "
              f"({total_checks - total_passed} failed)")
        sys.exit(1)


if __name__ == "__main__":
    main()
