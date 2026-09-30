#!/usr/bin/env python3
"""Publish the live retrieval-backend split as a shields badge (`data` branch `badges/retrieval.json`).

The decision this implements (owner, 2026-09-29): **publish `servedBy`, do not publish `mcpClients`.**

* `servedBy` is about *our own* implementation — how many searches today were answered by BM25 and how
  many fell back to the naive matcher — so publishing it is the same "make the invisible visible" move as
  the index endpoint's `textVersionCurrent`: it lets anyone outside check that a retrieval change is
  actually live, and see a degradation without asking a maintainer.
* `mcpClients` is about *other people* — per-client call counts, keyed on a self-declared
  `clientInfo.name` falling back to the User-Agent. It stays readable at `/api/analytics` but is
  deliberately **not** advertised: the number is a call count (not users), the key is self-reported, and
  publishing it would turn "who is using this" into public intelligence for very little gain.

The badge is a *snapshot of today*, because that is what the counter is: it resets with the day. The
label says so, and the counts themselves stay one request away at `/api/search-index` — the badge is a
signpost, not the record.

Usage:
    python3 scripts/update_retrieval_badge.py --out /tmp/badges/retrieval.json
    python3 scripts/update_retrieval_badge.py --source https://misakanet.org/api/search-index --print

Transport failures are deliberately **not** an error and write nothing: a badge that cannot be refreshed
should keep yesterday's value (with its own date visible on the endpoint) rather than publish "no data"
because a runner had a bad minute. The script prints what happened either way, and exits 1 only when the
service answered with something it cannot interpret — that is a shape change worth failing on.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = "https://misakanet.org/api/search-index"
DEFAULT_OUT = REPO / "badges" / "retrieval.json"
# Explicit UA, always: the edge answers 403 to Python urllib's default UA on this host (measured
# 2026-09-28, recorded in `docs/agents/repo-operations.md` §4). A probe that forgets this reads as an
# outage.
USER_AGENT = "misakanet-retrieval-badge/1.0 (+https://misakanet.org)"
UNREACHABLE = "unreachable"


def _pct(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


def badge_for(counts: dict | None) -> dict:
    """The shields payload for a `servedBy` map (`{"bm25": n, "fallback": m}`), or for no data.

    One number, because a badge holds one: the share answered by BM25. The colour carries the signal a
    reader actually cares about — a fallback is the *degraded* path, so zero is bright green, a trace is
    green, and a real share is orange rather than red: falling back is not a failure, it is the older
    answer path, and calling it an error would make the badge cry wolf.
    """
    counts = counts or {}
    bm25 = int(counts.get("bm25") or 0)
    fallback = int(counts.get("fallback") or 0)
    total = bm25 + fallback
    if total == 0:
        return {"schemaVersion": 1, "label": "retrieval today", "message": "no data", "color": "lightgrey"}
    share = fallback / total
    color = "brightgreen" if fallback == 0 else ("green" if share < 0.05 else "orange")
    return {"schemaVersion": 1, "label": "retrieval today", "message": f"{_pct(bm25, total)}% bm25",
            "color": color}


def fetch_index(source: str, timeout: int = 30, opener=None) -> tuple[str, dict | None]:
    """Read `servedBy` from the live index endpoint.

    Returns `(status, servedBy)` with status in `{"ok", UNREACHABLE}`. `opener` is the seam the tests use
    to drive both the request (so the User-Agent is asserted) and the answer (so each badge shape is).
    """
    request = urllib.request.Request(source, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    opener = opener or urllib.request.urlopen
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as error:   # noqa: BLE001
        print(f"retrieval badge: cannot read {source} ({type(error).__name__}: {error}) — nothing written",
              file=sys.stderr)
        return UNREACHABLE, None
    if not isinstance(payload, dict) or "servedBy" not in payload:
        raise SystemExit(
            f"the index endpoint no longer carries `servedBy` (keys: {sorted(payload)[:8] if isinstance(payload, dict) else type(payload).__name__}) "
            "— the badge would publish a number that means nothing, so this fails instead")
    return "ok", payload.get("servedBy") or {}


def write_badge(badge: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(badge, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--print", action="store_true", dest="print_badge", help="print instead of writing")
    args = parser.parse_args(argv)

    status, counts = fetch_index(args.source, timeout=args.timeout)
    if status == UNREACHABLE:
        return 0                       # keep yesterday's badge; the endpoint itself carries the date
    badge = badge_for(counts)
    if args.print_badge:
        print(json.dumps(badge, ensure_ascii=False))
    else:
        write_badge(badge, args.out)
        print(f"retrieval badge → {args.out}: {json.dumps(badge, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
