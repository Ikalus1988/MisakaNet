#!/usr/bin/env python3
"""
LessonReuseBench — Evaluate whether agents reuse prior failure lessons.

Usage:
    # Dry-run (no API keys needed)
    python3 scripts/lesson_reuse_bench.py --dry-run

    # Full run with agent
    python3 scripts/lesson_reuse_bench.py --agent openai --tasks tasks/reuse/

    # Compare with/without lesson pool
    python3 scripts/lesson_reuse_bench.py --agent claude --compare
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO / "tasks" / "reuse"
OUTPUT_FILE = REPO / "data" / "lesson_reuse_leaderboard.json"

# Scoring weights
WEIGHTS = {
    "task_b_pass": 0.40,
    "correct_lesson_retrieved": 0.20,
    "avoided_known_bad_path": 0.15,
    "generated_reusable_lesson": 0.15,
    "ci_pr_compliance": 0.10,
}


def load_task(path: Path) -> dict:
    """Load a task JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_task_pairs(tasks_dir: Path = None) -> list:
    """Load all A/B task pairs."""
    if tasks_dir is None:
        tasks_dir = TASKS_DIR
    pairs = {}
    for f in sorted(tasks_dir.glob("*.json")):
        task = load_task(f)
        pair_name = task.get("pair", f.stem)
        if pair_name not in pairs:
            pairs[pair_name] = {}
        phase = task.get("phase", "A")
        pairs[pair_name][phase] = task

    result = []
    for name, phases in pairs.items():
        if "A" in phases and "B" in phases:
            result.append({"name": name, "a": phases["A"], "b": phases["B"]})
    return result


def score_pair(pair: dict, result: dict) -> float:
    """Calculate score for a task pair result."""
    score = 0.0
    for dim, weight in WEIGHTS.items():
        if result.get(dim, False):
            score += weight
    return round(score, 3)


def run_dry(pairs: list) -> list:
    """Dry-run: validate tasks without running agents."""
    results = []
    for pair in pairs:
        name = pair["name"]
        a = pair["a"]
        b = pair["b"]

        # Validate task structure
        a_valid = all(k in a for k in ["name", "description", "expected_outcome"])
        b_valid = all(k in b for k in ["name", "description", "expected_outcome"])

        result = {
            "pair": name,
            "task_a_valid": a_valid,
            "task_b_valid": b_valid,
            "task_a_has_lesson_fields": "lesson_fields" in a.get("expected_outcome", {}),
            "task_b_has_relevant_lesson": "relevant_lesson" in b.get("setup", {}),
            "task_b_pass": True,  # assume pass for dry-run
            "correct_lesson_retrieved": b.get("setup", {}).get("lesson_pool_available", False),
            "avoided_known_bad_path": "avoids_dead_end" in b.get("expected_outcome", {}),
            "generated_reusable_lesson": a.get("expected_outcome", {}).get("lesson_generated", False),
            "ci_pr_compliance": True,
        }
        result["score"] = score_pair(pair, result)
        results.append(result)
    return results


def run_with_agent(pairs: list, agent: str, with_lessons: bool = True) -> list:
    """Run benchmark with an actual agent (placeholder for real integration)."""
    # TODO: integrate with actual agent execution
    # For now, return placeholder results
    results = []
    for pair in pairs:
        result = {
            "pair": pair["name"],
            "agent": agent,
            "with_lessons": with_lessons,
            "task_b_pass": False,
            "correct_lesson_retrieved": False,
            "avoided_known_bad_path": False,
            "generated_reusable_lesson": False,
            "ci_pr_compliance": False,
            "score": 0.0,
            "note": "Placeholder — integrate with agent execution"
        }
        results.append(result)
    return results


def generate_leaderboard(results: list, agent: str = "dry-run") -> dict:
    """Generate leaderboard entry."""
    total = sum(r["score"] for r in results) / len(results) if results else 0
    return {
        "agent": agent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pairs": results,
        "total_score": round(total, 3),
        "pair_count": len(results),
    }


def save_leaderboard(entry: dict, output_file: Path = None):
    """Append to leaderboard file."""
    if output_file is None:
        output_file = OUTPUT_FILE
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists():
        data = json.loads(output_file.read_text(encoding="utf-8"))
    else:
        data = []
    data.append(entry)
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="LessonReuseBench — evaluate agent lesson reuse")
    parser.add_argument("--dry-run", action="store_true", help="Validate tasks without running agents")
    parser.add_argument("--agent", default="dry-run", help="Agent to benchmark (openai, claude, etc.)")
    parser.add_argument("--tasks", default=str(TASKS_DIR), help="Task directory")
    parser.add_argument("--compare", action="store_true", help="Run with and without lesson pool")
    parser.add_argument("--output", help="Output file path")
    args = parser.parse_args()

    tasks_dir = Path(args.tasks)
    output_file = Path(args.output) if args.output else OUTPUT_FILE

    pairs = load_task_pairs(tasks_dir)
    if not pairs:
        print("No task pairs found in", tasks_dir)
        return

    print(f"Loaded {len(pairs)} task pairs: {[p['name'] for p in pairs]}")

    if args.dry_run:
        results = run_dry(pairs)
        for r in results:
            status = "[OK]" if r["score"] > 0.5 else "[WARN]"
            print(f"  {status} {r['pair']}: score={r['score']} (A valid={r['task_a_valid']}, B valid={r['task_b_valid']})")
        entry = generate_leaderboard(results, "dry-run")
        save_leaderboard(entry, output_file)
        print(f"\nTotal: {entry['total_score']}")
        print(f"Saved to: {output_file}")
    elif args.compare:
        print("\n--- With lesson pool ---")
        with_results = run_with_agent(pairs, args.agent, with_lessons=True)
        entry_with = generate_leaderboard(with_results, f"{args.agent}-with-lessons")
        for r in with_results:
            print(f"  {r['pair']}: score={r['score']}")

        print("\n--- Without lesson pool ---")
        without_results = run_with_agent(pairs, args.agent, with_lessons=False)
        entry_without = generate_leaderboard(without_results, f"{args.agent}-without-lessons")
        for r in without_results:
            print(f"  {r['pair']}: score={r['score']}")

        delta = round(entry_with["total_score"] - entry_without["total_score"], 3)
        print(f"\nLesson reuse delta: {delta}")
        entry_with["delta_vs_no_lesson"] = delta
        save_leaderboard(entry_with, output_file)
        save_leaderboard(entry_without, output_file)
    else:
        results = run_with_agent(pairs, args.agent)
        entry = generate_leaderboard(results, args.agent)
        for r in results:
            print(f"  {r['pair']}: score={r['score']}")
        print(f"\nTotal: {entry['total_score']}")
        save_leaderboard(entry, output_file)


if __name__ == "__main__":
    main()
