#!/usr/bin/env python3
"""Snapshot the live traffic counters into a static file the homepage can read.

Why a snapshot instead of the endpoint
-------------------------------------
`/api/analytics/traffic` is correct, public and cheap to *describe* — and far too slow to sit on a
visitor's critical path. Measured by hand on 2026-09-24, five consecutive requests:

    0.674s   0.659s   0.689s   17.426s   0.753s

The fast answers come from the worker's cache; the 17-second one is a recompute, which happens
whenever the counter has moved since the cache was filled — i.e. most of the time on a site that
is actually being used. A homepage panel calling it would be a 504 generator for a fraction of
visitors, which is precisely the failure #2151 spent a day removing (up to 100 parallel
`/api/github/…/comments` requests per homepage load). A static file cannot be slow, and it costs
the worker nothing.

That is also why this is not a worker change: the endpoint is fine where it is. It just must not be
called by a browser.

What it refuses to do matters more than what it does
----------------------------------------------------
* **Never write a zero because a fetch failed.** A traffic endpoint that is down is not a day
  without traffic, and `{"total": 0}` on the homepage is a lie that looks like data. A failed fetch
  leaves the previous file byte-for-byte as it was, and the process exits non-zero so the run is
  loud.
* **Never write a partial breakdown.** The four classes are the payload. A response missing one of
  them is not a smaller snapshot, it is a wrong one.
* **Never silently swallow a class it does not know.** If the worker starts reporting a fifth class,
  this fails rather than publishing a page that quietly drops it — the "we wrote a snapshot and the
  number went down" failure. The four known classes are listed below and asserted on both sides
  (`tests/test_sync_site_activity.py`, `tests/test_site_activity_panel.py`).
* **Never publish a total that disagrees with its own parts.** `total == sum(breakdown)` is checked
  because it is the cheapest proof that the response is complete rather than truncated mid-JSON.

Usage::

    python3 scripts/sync_site_activity.py                  # fetch, then write if it moved
    python3 scripts/sync_site_activity.py --force           # write even if nothing material changed
    python3 scripts/sync_site_activity.py --check           # validate the committed file, no network
    python3 scripts/sync_site_activity.py --base http://127.0.0.1:8123   # used by the tests

`--check` deliberately says nothing about the snapshot's **age**. The page prints the snapshot's own
date, so a stale file is visible to a reader; asserting freshness in CI would instead turn a broken
cron into a red required check that blocks every merge, which is a much worse trade than a date a
human can see.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = REPO / "docs" / "data" / "activity.json"
DEFAULT_BASE = "https://misakanet.org"
PATH = "/api/analytics/traffic"

# The classes the page has labels for, and therefore the only ones a snapshot may drop. Order is the
# order the page renders them in: the headline first, then the rest.
CALL_CLASSES = ("mcp", "agent", "crawler", "pageview")

# The exact keys of the published file. Pinned here so the page and this script cannot drift into
# reading a field the other does not write.
SNAPSHOT_KEYS = ("generated_at", "source", "date", "total", "calls")


class Refused(Exception):
    """The response (or the committed file) is not something this script will publish."""


def validate(snapshot: object, where: str = "snapshot") -> dict:
    """Return the snapshot if it is publishable, else raise Refused. Pure, so tests can call it."""
    if not isinstance(snapshot, dict):
        raise Refused(f"{where}: not an object")
    extra = sorted(set(snapshot) - set(SNAPSHOT_KEYS))
    missing = sorted(set(SNAPSHOT_KEYS) - set(snapshot))
    if missing:
        raise Refused(f"{where}: missing {missing}")
    if extra:
        raise Refused(f"{where}: unexpected key(s) {extra} — the page does not read them")
    date = snapshot["date"]
    if not isinstance(date, str):
        raise Refused(f"{where}: date is {type(date).__name__}, not a string")
    try:
        dt.date.fromisoformat(date)
    except ValueError as exc:
        raise Refused(f"{where}: date {date!r} is not ISO8601 — {exc}") from None
    calls = snapshot["calls"]
    if not isinstance(calls, dict) or not calls:
        raise Refused(f"{where}: calls is {calls!r}")
    unknown = sorted(set(calls) - set(CALL_CLASSES))
    if unknown:
        raise Refused(
            f"{where}: the endpoint reports class(es) {unknown} that this snapshot schema does not "
            f"know, so the page would drop them silently. Add them to CALL_CLASSES here and to the "
            f"page's labels (both locales) — do not publish a number with a hole in it."
        )
    missing_classes = [c for c in CALL_CLASSES if c not in calls]
    if missing_classes:
        raise Refused(f"{where}: calls is missing {missing_classes} — a partial breakdown")
    for name, value in calls.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise Refused(f"{where}: calls[{name!r}] is {value!r}, not a non-negative integer")
    total = snapshot["total"]
    if not isinstance(total, int) or isinstance(total, bool) or total < 0:
        raise Refused(f"{where}: total is {total!r}, not a non-negative integer")
    # A zero is not "no traffic": every visit to `/mcp` counts, and the endpoint itself does not
    # serve a zero for a live site. Refusing it is how a failed *upstream* aggregation is kept from
    # rendering as a real day.
    if total < 1:
        raise Refused(f"{where}: total is 0 — that is a fetch that failed, not a quiet day")
    if total != sum(calls.values()):
        raise Refused(
            f"{where}: total {total} != sum(calls) {sum(calls.values())} — the response is "
            f"inconsistent, which is what a truncated body looks like"
        )
    if not isinstance(snapshot["generated_at"], str) or not snapshot["generated_at"]:
        raise Refused(f"{where}: generated_at is {snapshot['generated_at']!r}")
    return snapshot


def snapshot_from(payload: object, source: str, now: dt.datetime | None = None) -> dict:
    """The published shape, built from the endpoint's own response."""
    if not isinstance(payload, dict):
        raise Refused(f"endpoint returned {type(payload).__name__}, not an object")
    breakdown = payload.get("breakdown")
    if not isinstance(breakdown, dict):
        raise Refused(f"endpoint returned no breakdown: {json.dumps(payload)[:200]}")
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return validate({
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": source,
        "date": payload.get("date"),
        "total": payload.get("total"),
        "calls": dict(breakdown),
    }, where="endpoint response")


def material(snapshot: dict) -> tuple:
    """What counts as a change worth a commit; `generated_at` is not part of it.

    A bot that opens a pull request every three hours to move a timestamp is churn in the one place
    where churn costs CI runs — `build-feed.yml` already lands one PR on that cadence, and this file
    rides in the same one.
    """
    return (snapshot["date"], snapshot["total"], tuple(sorted(snapshot["calls"].items())))


def fetch(url: str, attempts: int = 3, timeout: int = 60) -> dict:
    """GET the endpoint as JSON, retrying a slow first answer.

    The 17-second recompute is a normal response, not an error, so the timeout is generous and a
    single retry is worth more than a tight timeout: a snapshot that misses costs a whole cadence.
    """
    last = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "misakanet-site-activity"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
            return json.loads(body)
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:200]}"
        except Exception as exc:  # urllib raises a zoo of them; the message is the finding
            last = f"{type(exc).__name__}: {exc}"
        if attempt < attempts:
            print(f"  attempt {attempt} failed ({last}) — retrying")
    raise Refused(f"{url} could not be read after {attempts} attempt(s): {last}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=os.environ.get("MISAKANET_BASE", DEFAULT_BASE),
                        help=f"site to read the counters from (default {DEFAULT_BASE})")
    parser.add_argument("--out", default=str(OUTPUT), help="file to write")
    parser.add_argument("--check", action="store_true",
                        help="validate the committed file and exit (no network, no write)")
    parser.add_argument("--force", action="store_true",
                        help="write even when nothing material changed")
    args = parser.parse_args()
    out = pathlib.Path(args.out)

    if args.check:
        if not out.is_file():
            print(f"::error::{out} does not exist — the homepage reads it and would render nothing")
            return 1
        try:
            validate(json.loads(out.read_text(encoding="utf-8")), where=str(out))
        except (Refused, json.JSONDecodeError) as exc:
            print(f"::error::{exc}")
            return 1
        print(f"{out} is a valid snapshot")
        return 0

    source = urllib.parse.urljoin(args.base.rstrip("/") + "/", PATH.lstrip("/"))
    print(f"reading {source}")
    try:
        snap = snapshot_from(fetch(source), source)
    except Refused as exc:
        # The previous file is deliberately left alone: a failed fetch is not a quiet day.
        print(f"::error::refusing to write a snapshot — {exc}")
        print(f"  {out} is unchanged (last date: "
              f"{(json.loads(out.read_text()).get('date') if out.is_file() else 'absent')})")
        return 1

    if out.is_file() and not args.force:
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None
        if isinstance(previous, dict) and material(previous) == material(snap):
            print(f"no material change ({snap['date']} total={snap['total']}) — nothing to write")
            return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"wrote {out}: {snap['date']} total={snap['total']} {snap['calls']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
