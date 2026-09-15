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
from pathlib import Path


def read_counter_file(repo_root: Path) -> dict:
    """Read node counter from data/counter.json.

    The file is a *mirror* of the live counter, refreshed by ``--mirror`` (daily job); the
    authoritative value is the worker's KV counter behind /api/counter.
    """
    counter_path = repo_root / "data" / "counter.json"
    if not counter_path.exists():
        return {"current": None, "updated": None}
    try:
        data = json.loads(counter_path.read_text(encoding="utf-8"))
        return {"current": data.get("current"), "updated": data.get("updated", "?")[:10]}
    except (json.JSONDecodeError, OSError):
        return {"current": None, "updated": None}


def read_test_nodes(repo_root: Path) -> list:
    """Read test/non-formal node IDs (legacy, returns empty)."""
    return []


COUNTER_URL = "https://misakanet.org/api/counter"
# Cloudflare in front of the endpoint answers 403 to urllib's default User-Agent, so the
# request identifies itself (found 2026-09-15: curl worked, urllib did not).
USER_AGENT = "misakanet-node-status/1.0 (+https://misakanet.org)"


def fetch_counter(url: str = COUNTER_URL, timeout: float = 20.0) -> dict:
    """GET /api/counter, which serves the KV counter when it is bound."""
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:   # noqa: S310 (fixed https)
        return json.loads(response.read().decode("utf-8"))


def mirror_counter(repo_root: Path, payload: dict, *, today: str | None = None) -> int | None:
    """Write the live counter into ``data/counter.json`` when it is ahead. Returns the new value.

    ``data/counter.json`` was written only by the issue-based registration workflow, while
    every MCP registration (the npx installer's path) incremented the worker's KV counter —
    two independent sequences for one fact. By 2026-09-15 the file said 10073 and KV said
    10178: the site showed 178 nodes, the file implied 73, and nothing watched (issue #1683).

    Monotonic on purpose: a payload that is *behind* the file means the endpoint fell back to
    its GitHub copy or the KV read failed, and rewriting the file with it would move the
    published count backwards. A malformed payload is refused for the same reason.
    """
    from datetime import datetime, timezone

    current = payload.get("current")
    if not isinstance(current, int) or isinstance(current, bool) or current <= 0:
        raise ValueError(f"counter payload has no usable 'current': {payload!r}")

    path = repo_root / "data" / "counter.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    have = data.get("current")
    if isinstance(have, int) and current <= have:
        return None

    data["current"] = current
    data["updated"] = today or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return current


def main():
    parser = argparse.ArgumentParser(description="MisakaNet node status dashboard")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--mirror", action="store_true",
                        help="read the live counter and refresh data/counter.json when it is behind")
    parser.add_argument("--url", default=COUNTER_URL, help=argparse.SUPPRESS)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    if args.mirror:
        try:
            payload = fetch_counter(args.url)
        except Exception as exc:                     # offline, DNS, non-JSON: leave the file alone
            print(f"❌ could not read the live counter ({exc}) — data/counter.json left alone",
                  file=sys.stderr)
            return 1
        try:
            mirrored = mirror_counter(repo_root, payload)
        except ValueError as exc:
            print(f"❌ refusing to mirror: {exc}", file=sys.stderr)
            return 1
        print("✅ data/counter.json already matches the live counter"
              if mirrored is None else f"✅ data/counter.json ← {mirrored} (live counter)")
        return 0

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
    # raise/SystemExit, not a bare call: `main()` returning 1 used to be discarded, so a
    # failing run still exited 0 — the mirror job would have committed a guess (found by
    # tests/test_node_status.py, 2026-09-15).
    raise SystemExit(main())
