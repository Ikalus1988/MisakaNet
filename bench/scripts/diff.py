"""Diff utility for comparing two benchmark runs."""

from typing import Any, Dict, List, Tuple


def compare_runs(baseline: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two benchmark result dictionaries.
    
    Returns a dict with:
    - baseline_run_id, current_run_id
    - baseline_seed, current_seed
    - regressions: list of regression descriptions
    - improvements: list of improvement descriptions
    - task_changes: list of tasks with outcome changes
    - metric_changes: dict of metric deltas
    """
    result = {
        "baseline_run_id": baseline.get("run_id", "unknown"),
        "current_run_id": current.get("run_id", "unknown"),
        "baseline_seed": baseline.get("seed", "unknown"),
        "current_seed": current.get("seed", "unknown"),
        "regressions": [],
        "improvements": [],
        "task_changes": [],
        "metric_changes": {}
    }
    
    # Compare task outcomes
    baseline_tasks = baseline.get("tasks", {})
    current_tasks = current.get("tasks", {})
    all_tasks = set(baseline_tasks.keys()) | set(current_tasks.keys())
    
    for task in sorted(all_tasks):
        base_task = baseline_tasks.get(task, {})
        curr_task = current_tasks.get(task, {})
        
        base_success = base_task.get("success", False)
        curr_success = curr_task.get("success", False)
        
        if base_success != curr_success:
            change = {
                "task": task,
                "baseline_success": base_success,
                "current_success": curr_success,
                "baseline_error": base_task.get("error"),
                "current_error": curr_task.get("error")
            }
            result["task_changes"].append(change)
            
            if base_success and not curr_success:
                result["regressions"].append(f"Task '{task}' regressed: success -> failure")
            elif not base_success and curr_success:
                result["improvements"].append(f"Task '{task}' improved: failure -> success")
    
    # Compare summary metrics
    base_summary = baseline.get("summary", {})
    curr_summary = current.get("summary", {})
    
    metrics_to_compare = [
        ("passed", "higher_is_better"),
        ("failed", "lower_is_better"),
        ("total_latency_ms", "lower_is_better"),
        ("total_cost_usd", "lower_is_better")
    ]
    
    for metric, direction in metrics_to_compare:
        base_val = base_summary.get(metric, 0)
        curr_val = curr_summary.get(metric, 0)
        
        if base_val != curr_val:
            delta = curr_val - base_val
            result["metric_changes"][metric] = {
                "baseline": base_val,
                "current": curr_val,
                "delta": delta
            }
            
            is_regression = (direction == "higher_is_better" and delta < 0) or \
                           (direction == "lower_is_better" and delta > 0)
            
            if is_regression:
                result["regressions"].append(
                    f"{metric} regressed: {base_val} -> {curr_val} ({delta:+d})"
                )
            else:
                result["improvements"].append(
                    f"{metric} improved: {base_val} -> {curr_val} ({delta:+d})"
                )
    
    # Compare per-task metrics (latency, cost)
    for task in sorted(all_tasks):
        base_task = baseline_tasks.get(task, {})
        curr_task = current_tasks.get(task, {})
        
        for metric in ["latency_ms", "cost_usd"]:
            base_val = base_task.get(metric, 0)
            curr_val = curr_task.get(metric, 0)
            
            if base_val != curr_val:
                key = f"{task}.{metric}"
                delta = curr_val - base_val
                result["metric_changes"][key] = {
                    "baseline": base_val,
                    "current": curr_val,
                    "delta": delta
                }
                
                if delta > 0:  # Higher latency/cost is regression
                    result["regressions"].append(
                        f"{task}.{metric} increased: {base_val} -> {curr_val} ({delta:+.2f})"
                    )
                else:
                    result["improvements"].append(
                        f"{task}.{metric} decreased: {base_val} -> {curr_val} ({delta:+.2f})"
                    )
    
    return result


def format_diff_markdown(diff: Dict[str, Any]) -> str:
    """Format diff as markdown for CI reports."""
    lines = [
        "## Benchmark Diff Report",
        "",
        f"**Baseline:** `{diff['baseline_run_id']}` (seed={diff['baseline_seed']})  ",
        f"**Current:** `{diff['current_run_id']}` (seed={diff['current_seed']})  ",
        ""
    ]
    
    if diff["regressions"]:
        lines.append("### 🔴 Regressions")
        lines.append("")
        for reg in diff["regressions"]:
            lines.append(f"- {reg}")
        lines.append("")
    
    if diff["improvements"]:
        lines.append("### 🟢 Improvements")
        lines.append("")
        for imp in diff["improvements"]:
            lines.append(f"- {imp}")
        lines.append("")
    
    if diff["task_changes"]:
        lines.append("### 📋 Task Outcome Changes")
        lines.append("")
        lines.append("| Task | Baseline | Current |")
        lines.append("|------|----------|---------|")
        for change in diff["task_changes"]:
            base = "✅ Pass" if change["baseline_success"] else f"❌ Fail ({change['baseline_error']})"
            curr = "✅ Pass" if change["current_success"] else f"❌ Fail ({change['current_error']})"
            lines.append(f"| {change['task']} | {base} | {curr} |")
        lines.append("")
    
    if diff["metric_changes"]:
        lines.append("### 📊 Metric Changes")
        lines.append("")
        lines.append("| Metric | Baseline | Current | Delta |")
        lines.append("|--------|----------|---------|-------|")
        for metric, change in diff["metric_changes"].items():
            lines.append(f"| {metric} | {change['baseline']} | {change['current']} | {change['delta']:+.2f} |")
        lines.append("")
    
    if not diff["regressions"] and not diff["improvements"] and not diff["task_changes"]:
        lines.append("✅ No changes detected between runs.")
    
    return "\n".join(lines)


def main():
    """CLI entry point for diff.py."""
    import argparse
    import json
    import sys
    from pathlib import Path
    
    parser = argparse.ArgumentParser(description="Compare two benchmark runs")
    parser.add_argument("baseline", help="Path to baseline results.json")
    parser.add_argument("current", help="Path to current results.json")
    parser.add_argument("--format", choices=["json", "text", "markdown"], default="text")
    parser.add_argument("--output", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    with open(args.baseline) as f:
        baseline = json.load(f)
    with open(args.current) as f:
        current = json.load(f)
    
    diff = compare_runs(baseline, current)
    
    if args.format == "json":
        output = json.dumps(diff, indent=2)
    elif args.format == "markdown":
        output = format_diff_markdown(diff)
    else:
        # Text format
        from orchestrator import print_diff
        import io
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        print_diff(diff)
        sys.stdout = old_stdout
        output = buf.getvalue()
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
