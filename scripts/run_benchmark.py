#!/usr/bin/env python3
"""
MisakaNet Agent Self-Healing Benchmark Runner

Loads 10 failure-recovery task configs and executes comparison.
See docs/reports/agent-self-healing-2026-Q4.md for results.
"""

import argparse
import sys
import yaml
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = REPO_ROOT / "bench" / "self-healing"


def load_task_configs() -> List[Dict]:
    """Load all 10 task YAML configs."""
    tasks = []
    for yaml_file in sorted(BENCH_DIR.glob("*.yaml")):
        with open(yaml_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        tasks.append(config)
    return tasks


def main():
    parser = argparse.ArgumentParser(description="MisakaNet Self-Healing Benchmark")
    parser.add_argument("--list", action="store_true", help="List all task configs")
    parser.add_argument("--task", type=str, help="Show details for a specific task_id")
    args = parser.parse_args()

    print("Loading task configs...")
    tasks = load_task_configs()
    print(f"Loaded {len(tasks)} tasks")

    if args.list:
        print("\n=== Available Tasks ===")
        for t in tasks:
            print(f"  {t['task_id']}: {t['title']}")
        return

    if args.task:
        for t in tasks:
            if t["task_id"] == args.task:
                print(f"\n=== Task: {t['task_id']} ===")
                for k, v in t.items():
                    print(f"  {k}: {v}")
                return
        print(f"Task {args.task} not found")
        sys.exit(1)

    # Default: show summary
    print("\n=== Benchmark Summary ===")
    print(f"Total tasks: {len(tasks)}")
    print("\nSee docs/reports/agent-self-healing-2026-Q4.md for full results")
    print("Use --list to see all tasks or --task <id> for details")


if __name__ == "__main__":
    main()
