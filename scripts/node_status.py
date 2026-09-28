#!/usr/bin/env python3
"""Node status dashboard — read the live node counter and the corpus size.

Usage:
    python3 scripts/node_status.py                 # human-readable
    python3 scripts/node_status.py --json          # machine-readable

Output:
    Node Counter:     15774
    Latest Node ID:   Misaka15774
    Counter updated:  2026-09-27
    Lessons:          418

The counter is read from `https://misakanet.org/api/counter`, which serves D1 (or its KV fallback)
and **only** those: the endpoint's last-resort read of `data/counter.json` was removed on 2026-09-28,
and this script's own `--mirror` mode (and the `sync-node-counter.yml` job that called it) went with
it. The file was a second copy of one number, and the wrong shape for it: `/api/counter` is read to
predict the id the next registrant is handed, so a mirror that can be days behind — issue #1820 was
filed when the `data` branch's copy was frozen 3.5 months earlier — is worse than no answer.

So this script no longer reads or writes a file at all. When the endpoint cannot answer, it says so
and exits 1 rather than printing a number from somewhere else. `data/counter.json` is not "kept for
offline use": it was deleted in the same change, because a copy nobody writes is a number that only
looks authoritative.
"""
import argparse
import json
import sys
from pathlib import Path

COUNTER_URL = "https://misakanet.org/api/counter"
# Cloudflare in front of the endpoint answers 403 to urllib's default User-Agent, so the
# request identifies itself (found 2026-09-15: curl worked, urllib did not).
USER_AGENT = "misakanet-node-status/1.0 (+https://misakanet.org)"


def fetch_counter(url: str = COUNTER_URL, timeout: float = 20.0) -> dict:
    """GET /api/counter, which serves the durable counter when it is bound."""
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:   # noqa: S310 (fixed https)
        return json.loads(response.read().decode("utf-8"))


def usable_current(payload: object) -> int | None:
    """The payload's `current` when it is a usable allocation counter, else None.

    Same rule as `scripts/register_issue.py` (which fills a welcome comment from the same endpoint):
    an int, not a bool, positive. `/api/counter` answers `{current: null, source: "unavailable"}` with
    a 503 when neither store answered, and a 5xx body parsed as JSON is exactly the shape that would
    otherwise print `Node Counter: None` or, worse, `0`.
    """
    if not isinstance(payload, dict):
        return None
    current = payload.get("current")
    if not isinstance(current, int) or isinstance(current, bool) or current <= 0:
        return None
    return current


def count_lessons(repo_root: Path) -> int:
    """Lesson files on disk — the raw count, not the published index (`data/lessons.json`)."""
    lessons_dir = repo_root / "lessons"
    total = 0
    for subdir in ("core", "contrib"):
        directory = lessons_dir / subdir
        if directory.exists():
            total += len(list(directory.glob("*.md")))
    return total


def main():
    parser = argparse.ArgumentParser(description="MisakaNet node status dashboard")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--url", default=COUNTER_URL, help=argparse.SUPPRESS)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    try:
        payload = fetch_counter(args.url)
    except Exception as exc:                     # offline, DNS, 503, non-JSON: there is no value
        print(f"❌ could not read the live counter ({exc})", file=sys.stderr)
        print("   There is no local fallback any more: `data/counter.json` was deleted on 2026-09-28 "
              "(it could be months behind, #1820). Retry when the endpoint answers, or read the "
              "durable counter directly if you have Cloudflare access.", file=sys.stderr)
        return 1

    counter = usable_current(payload)
    latest_id = f"Misaka{str(counter).zfill(5)}" if counter else "unknown"
    updated = payload.get("updated") if isinstance(payload, dict) else None
    lesson_count = count_lessons(repo_root)

    if args.json:
        print(json.dumps({
            "counter": counter,
            "latest_node_id": latest_id,
            "counter_updated": updated,
            "source": payload.get("source", "durable-store") if isinstance(payload, dict) else None,
            "lesson_count": lesson_count,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Node Counter:     {counter or 'unknown'}")
        print(f"Latest Node ID:   {latest_id}")
        print(f"Counter updated:  {updated or '?'}")
        print(f"Lessons (files):  {lesson_count}")

    # A 2xx whose body carries no usable counter is still an unavailable answer: exit 1 so a caller
    # scripting this notices, instead of reading "unknown" as a value.
    return 0 if counter else 1


if __name__ == "__main__":
    # raise/SystemExit, not a bare call: `main()` returning 1 used to be discarded, so a
    # failing run still exited 0 — the mirror job would have committed a guess (found by
    # tests/test_node_status.py, 2026-09-15).
    raise SystemExit(main())
