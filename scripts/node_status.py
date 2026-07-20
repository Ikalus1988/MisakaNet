#!/usr/bin/env python3
"""Node status dashboard — read MisakaNet KV to display node stats.

Usage:
    # Via wrangler (requires Cloudflare auth)
    python3 scripts/node_status.py

    # Or pass KV namespace ID directly
    python3 scripts/node_status.py --kv-id d5fb6b0797b84d17b0586fb982231ffe

Output:
    Node Counter: 10060
    Latest Node ID: Misaka00060
    Active Nodes (sampled): 5
"""
import argparse
import json
import subprocess
import sys


def read_counter_file(repo_root: Path) -> dict:
    """Read node counter from data/counter.json (source of truth)."""
    counter_path = repo_root / "data" / "counter.json"
    if not counter_path.exists():
        return {"current": None, "updated": None}
    try:
        data = json.loads(counter_path.read_text(encoding="utf-8"))
        return {"current": data.get("current"), "updated": data.get("updated", "?")[:10]}
    except (json.JSONDecodeError, OSError):
        return {"current": None, "updated": None}


def read_test_nodes(repo_root: Path) -> list:
    """Read test/non-formal node IDs from test-nodes.json."""
    test_path = repo_root / "test-nodes.json"
    if not test_path.exists():
        return []
    try:
        data = json.loads(test_path.read_text(encoding="utf-8"))
        return data.get("tests", [])
    except (json.JSONDecodeError, OSError):
        return []


def main():
    parser = argparse.ArgumentParser(description="MisakaNet node status dashboard")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    # Read from data/counter.json (source of truth)
    counter_info = read_counter_file(repo_root)
    counter = counter_info["current"]
    latest_id = f"Misaka{str(counter).zfill(5)}" if counter else "unknown"
    test_nodes = read_test_nodes(repo_root)

    # Count lessons
    lessons_dir = repo_root / "lessons"
    lesson_count = 0
    for subdir in ("core", "contrib"):
        d = lessons_dir / subdir
        if d.exists():
            lesson_count += len(list(d.glob("*.md")))

    if args.json:
        print(json.dumps({
            "counter": counter,
            "latest_node_id": latest_id,
            "counter_updated": counter_info["updated"],
            "test_nodes_count": len(test_nodes),
            "lesson_count": lesson_count,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Node Counter:     {counter or 'unknown'}")
        print(f"Latest Node ID:   {latest_id}")
        print(f"Counter updated:  {counter_info['updated']}")
        print(f"Test nodes:       {len(test_nodes)} (excluded from active count)")
        print(f"Lessons:          {lesson_count}")


if __name__ == "__main__":
    main()
