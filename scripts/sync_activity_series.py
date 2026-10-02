#!/usr/bin/env python3
"""Snapshot the activity **trend** into a static file the homepage's chart can fall back to.

`docs/data/activity.json` holds one day. This writes `docs/data/activity-series.json` — the same
counters as a daily series — so the "Network activity" panel can answer "is the network busier than
it was last week?" instead of only "how many calls today?" (issue #2521, option A).

Where the numbers come from, and what they are not
--------------------------------------------------
`GET /api/activity/history`, the anonymous, edge-cached projection of **our own** call counters
(`counters` rows of `scope='traffic'`, one per day per class — the same reader `/api/activity` uses
for today). This is not Cloudflare's edge analytics: no status codes, no cache-hit ratio, no bytes,
no colo. Those need a read-only Cloudflare credential that does not exist yet (`CF_OBSERVABILITY_TOKEN`
is aspirational — see docs/maintainer/credentials-and-environments.md §2), and until it does, the
chart must say it is drawing our own call counts. `source` in the file records the route this snapshot
was read from (the sibling script's convention); the route's own `source` field names the computation
behind the numbers and is what the live panel reads.

The snapshot is the *fallback*, exactly as `activity.json` is: the panel prefers the live route and
reads this file when the route is unreachable. It rides in `build-feed.yml`'s existing three-hourly
job so a fallback nothing writes is not a fallback.

What it refuses to do matters more than what it does
----------------------------------------------------
* **Never write a series because a fetch failed.** A failed fetch leaves the previous file
  byte-for-byte as it was and exits non-zero — the same rule as `sync_site_activity.py`, for the same
  reason: a chart is more persuasive than a number and therefore more dangerous when wrong.
* **Never publish a gap it cannot see.** The series must be strictly ascending ISO dates with no
  repeats and no hole, and `window` must agree with the first and last of them. A chart's x-axis is
  the part that lies quietly when a day goes missing.
* **Never publish a partial day.** Each day needs all four classes (`mcp`, `agent`, `crawler`,
  `pageview`) and `total == sum(calls)` — the cheapest proof the body was not truncated mid-JSON.
  An unknown fifth class is a hard error rather than a silently dropped bar.
* **Never publish a flat zero week.** `total == 0` for *every* day is a store that could not be read
  wearing a quiet week's clothes. The route refuses to serve that shape (503
  `counters_unreadable`), and this script refuses to write it — the panel then shows no chart at all,
  which is the designed degradation and not an empty one.
* **Never grow the file into an unbounded log.** The published window is the endpoint's own (`window.days`,
  clamped there to 2–30); a longer window is fetched explicitly with `--days`, not accumulated here.

Usage::

    python3 scripts/sync_activity_series.py                  # fetch, then write if it moved
    python3 scripts/sync_activity_series.py --days 14        # fetch a two-week window
    python3 scripts/sync_activity_series.py --force          # write even if nothing material changed
    python3 scripts/sync_activity_series.py --check          # validate the committed file, no network
    python3 scripts/sync_activity_series.py --from-committed-snapshots
    python3 scripts/sync_activity_series.py --base http://127.0.0.1:8123   # used by the tests

`--check` treats an **absent** file as fine, deliberately, and unlike `sync_site_activity.py`. That
file is the fallback for the panel's headline numbers, so its absence is a broken page; this one only
adds a chart, and "no chart" is what the panel renders when it has no series — a designed state, not
a failure. A *present* file is validated as strictly as the endpoint's response.

Bootstrapping from what the repository already measured
-------------------------------------------------------
`--from-committed-snapshots` writes a series out of the **git history of `docs/data/activity.json`**
— the snapshots this job has been committing every three hours since 2026-09-24. It exists for the
window before `/api/activity/history` is deployed (and for a chart that would otherwise be empty
until then), and it is the one mode whose numbers are **lower bounds** rather than day totals: the
last snapshot of a day was taken before that day ended, so it is "the day's count at 21:40Z", not
"the day's count". Every point is a real committed measurement, and the file says where it came from
(`source` begins with `git-history:`) so the chart can label the shape honestly and so a later run
from the live route can replace it wholesale. Today is always dropped: a day still in progress has no
final value to be a lower bound *of*.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = REPO / "docs" / "data" / "activity-series.json"
DEFAULT_BASE = "https://misakanet.org"
PATH = "/api/activity/history"
DEFAULT_DAYS = 7

# The classes the page has labels for (`ACTIVITY_CLASSES` in docs/index.html) and therefore the only
# ones a day may be made of. Compared against that list by tests/test_activity_history_panel.py.
CALL_CLASSES = ("mcp", "agent", "crawler", "pageview")

# The exact keys of the published file and of each of its days. Pinned here so the page and this
# script cannot drift into reading a field the other does not write.
SERIES_KEYS = ("generated_at", "source", "window", "series")
DAY_KEYS = ("date", "total", "calls")
WINDOW_KEYS = ("from", "to", "days")


class Refused(Exception):
    """The response (or the committed file) is not something this script will publish."""


def _require_int(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise Refused(f"{where} is {value!r}, not a non-negative integer")
    return value


def validate(snapshot: object, where: str = "snapshot") -> dict:
    """Return the snapshot if it is publishable, else raise Refused. Pure, so tests can call it."""
    if not isinstance(snapshot, dict):
        raise Refused(f"{where}: not an object")
    extra = sorted(set(snapshot) - set(SERIES_KEYS))
    missing = sorted(set(SERIES_KEYS) - set(snapshot))
    if missing:
        raise Refused(f"{where}: missing {missing}")
    if extra:
        raise Refused(f"{where}: unexpected key(s) {extra} — the page does not read them")

    window = snapshot["window"]
    if not isinstance(window, dict):
        raise Refused(f"{where}: window is {window!r}")
    window_extra = sorted(set(window) - set(WINDOW_KEYS))
    window_missing = sorted(set(WINDOW_KEYS) - set(window))
    if window_missing or window_extra:
        raise Refused(f"{where}: window keys are {sorted(window)} — expected {sorted(WINDOW_KEYS)}")
    span = _require_int(window["days"], f"{where}: window.days")
    if span < 1:
        raise Refused(f"{where}: window.days is {span} — an empty window is not a series")
    for key in ("from", "to"):
        value = window[key]
        if not isinstance(value, str):
            raise Refused(f"{where}: window.{key} is {value!r}, not an ISO date")
        try:
            dt.date.fromisoformat(value)
        except ValueError as exc:
            raise Refused(f"{where}: window.{key} {value!r} is not ISO8601 — {exc}") from None

    series = snapshot["series"]
    if not isinstance(series, list) or not series:
        raise Refused(f"{where}: series is {series!r}")
    if len(series) != span:
        raise Refused(
            f"{where}: window.days says {span} but the series holds {len(series)} — the axis would "
            f"be drawn to the wrong width"
        )

    seen: list[str] = []
    any_nonzero = False
    for index, day in enumerate(series):
        label = f"{where}: series[{index}]"
        if not isinstance(day, dict):
            raise Refused(f"{label}: not an object")
        day_extra = sorted(set(day) - set(DAY_KEYS))
        day_missing = sorted(set(DAY_KEYS) - set(day))
        if day_missing or day_extra:
            raise Refused(f"{label}: keys are {sorted(day)} — expected {sorted(DAY_KEYS)}")
        date = day["date"]
        if not isinstance(date, str):
            raise Refused(f"{label}: date is {date!r}, not a string")
        try:
            dt.date.fromisoformat(date)
        except ValueError as exc:
            raise Refused(f"{label}: date {date!r} is not ISO8601 — {exc}") from None
        seen.append(date)

        calls = day["calls"]
        if not isinstance(calls, dict) or not calls:
            raise Refused(f"{label}: calls is {calls!r}")
        unknown = sorted(set(calls) - set(CALL_CLASSES))
        if unknown:
            raise Refused(
                f"{label}: the endpoint reports class(es) {unknown} that this schema does not know, "
                f"so the chart would drop them silently. Add them to CALL_CLASSES here and to the "
                f"page's labels (both locales) — do not publish a bar with a hole in it."
            )
        missing_classes = [c for c in CALL_CLASSES if c not in calls]
        if missing_classes:
            raise Refused(f"{label}: calls is missing {missing_classes} — a partial day")
        for name, value in calls.items():
            _require_int(value, f"{label}: calls[{name!r}]")
        total = _require_int(day["total"], f"{label}: total")
        if total != sum(calls.values()):
            raise Refused(
                f"{label}: total {total} != sum(calls) {sum(calls.values())} — the response is "
                f"inconsistent, which is what a truncated body looks like"
            )
        if total > 0:
            any_nonzero = True

    if seen != sorted(seen):
        raise Refused(f"{where}: the series is not in date order: {seen}")
    if len(set(seen)) != len(seen):
        raise Refused(f"{where}: the series repeats a date: {seen}")
    for previous, current in zip(seen, seen[1:]):
        if (dt.date.fromisoformat(current) - dt.date.fromisoformat(previous)).days != 1:
            raise Refused(
                f"{where}: {previous} is followed by {current} — a hole in the series. A chart joins "
                f"those two points as if the gap were a slope; refuse instead."
            )
    if seen[0] != window["from"] or seen[-1] != window["to"]:
        raise Refused(
            f"{where}: window is {window['from']}..{window['to']} but the series is "
            f"{seen[0]}..{seen[-1]}"
        )
    if not any_nonzero:
        raise Refused(
            f"{where}: every day totals 0 — that is a store that could not be read, not a quiet "
            f"week. Publishing it would draw a flat, true-looking week."
        )
    if not isinstance(snapshot["generated_at"], str) or not snapshot["generated_at"]:
        raise Refused(f"{where}: generated_at is {snapshot['generated_at']!r}")
    if not isinstance(snapshot["source"], str) or not snapshot["source"]:
        raise Refused(f"{where}: source is {snapshot['source']!r} — the file has to say where it came from")
    return snapshot


def snapshot_from(payload: object, source: str, now: dt.datetime | None = None) -> dict:
    """The published shape, built from the endpoint's own response.

    `source` is the URL this script read (as `sync_site_activity` records it), not the endpoint's own
    `source` field: the file is the only record of where *these* numbers came from, and a reader of
    the file should not have to be told which route produced it. The endpoint's `source` names the
    computation behind the numbers (`/api/analytics/traffic`) and is what the live route publishes.
    """
    if not isinstance(payload, dict):
        raise Refused(f"endpoint returned {type(payload).__name__}, not an object")
    window = payload.get("window")
    series = payload.get("series")
    if not isinstance(window, dict) or not isinstance(series, list):
        raise Refused(f"endpoint returned no window/series: {json.dumps(payload)[:200]}")
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return validate({
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": source,
        "window": dict(window),
        "series": [dict(day) for day in series],
    }, where="endpoint response")


def snapshot_from_committed(days: int = DEFAULT_DAYS, repo: pathlib.Path = REPO,
                            now: dt.datetime | None = None) -> dict:
    """A series built from the snapshots this repository already committed.

    `docs/data/activity.json` has been written every three hours since 2026-09-24, and each version
    in git is a real measurement of that moment's counters. Taking, per date, the entry with the
    highest `total` gives the last measurement of that day — which is a **lower bound** on the day's
    total, because the day had not ended. That is honest as long as the file says so, which is what
    the `git-history:` source prefix is for.

    Today is dropped: it is still being counted, so it has no value to be a lower bound of.
    """
    if days < 1:
        raise Refused(f"--days must be positive, got {days}")
    listing = subprocess.run(
        ["git", "log", "--since=60.days.ago", "--format=%H", "--", "docs/data/activity.json"],
        cwd=repo, capture_output=True, text=True,
    )
    if listing.returncode != 0:
        raise Refused(f"git log failed: {listing.stderr.strip()[:200]}")
    best: dict[str, dict] = {}
    for sha in listing.stdout.split():
        shown = subprocess.run(
            ["git", "show", f"{sha}:docs/data/activity.json"],
            cwd=repo, capture_output=True, text=True,
        )
        if shown.returncode != 0:
            continue  # the path did not exist at that commit; not a failure
        try:
            snap = json.loads(shown.stdout)
        except json.JSONDecodeError:
            continue  # a committed file that did not parse is not evidence of anything
        date = snap.get("date")
        total = snap.get("total")
        calls = snap.get("calls")
        if not isinstance(date, str) or not isinstance(total, int) or not isinstance(calls, dict):
            continue
        # Highest total wins rather than "last commit wins": a commit order is not a measurement
        # order, and a snapshot that was reverted would otherwise overwrite the better one.
        if date not in best or total > best[date]["total"]:
            best[date] = {"date": date, "total": total, "calls": dict(calls)}

    today = (now or dt.datetime.now(dt.timezone.utc)).date().isoformat()
    dates = sorted(d for d in best if d < today)
    if not dates:
        raise Refused("no committed snapshot of a finished day was found in the last 60 days")
    # A chart joins neighbouring points as if the gap were a slope, so the window is a *contiguous*
    # stretch of days — and the newest such stretch of at least two days, because an isolated newest
    # point is not a trend of its own. One window with a hole in it is refused rather than drawn.
    run: list[str] = []
    for end in range(len(dates) - 1, -1, -1):
        candidate = [dates[end]]
        for date in reversed(dates[:end]):
            if (dt.date.fromisoformat(candidate[-1]) - dt.date.fromisoformat(date)).days == 1:
                candidate.append(date)
            else:
                break
        if len(candidate) >= 2:
            run = list(reversed(candidate))
            break
    if not run:
        raise Refused("no two consecutive days of committed snapshots — not a trend")
    window = run[-days:]
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return validate({
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": "git-history:docs/data/activity.json",
        "window": {"from": window[0], "to": window[-1], "days": len(window)},
        "series": [best[date] for date in window],
    }, where="committed snapshots")


def material(snapshot: dict) -> tuple:
    """What counts as a change worth a commit; `generated_at` is not part of it.

    Same trade as `sync_site_activity.material`: a bot that opens a pull request every three hours to
    move a timestamp is churn in the one place where churn costs CI runs. The window and the numbers
    are the content; when is not.
    """
    return (
        tuple((key, snapshot["window"][key]) for key in sorted(WINDOW_KEYS)),
        tuple(
            (day["date"], day["total"], tuple(sorted(day["calls"].items())))
            for day in snapshot["series"]
        ),
    )


def fetch(url: str, attempts: int = 3, timeout: int = 60) -> dict:
    """GET the endpoint as JSON, retrying a slow first answer. Same shape as the sibling script."""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "misakanet-activity-series"})
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
                        help=f"site to read the series from (default {DEFAULT_BASE})")
    parser.add_argument("--out", default=str(OUTPUT), help="file to write")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"window length to ask for (default {DEFAULT_DAYS}; the endpoint clamps it)")
    parser.add_argument("--check", action="store_true",
                        help="validate the committed file and exit (no network, no write)")
    parser.add_argument("--force", action="store_true",
                        help="write even when nothing material changed")
    parser.add_argument("--from-committed-snapshots", action="store_true",
                        help="build the series from this repository's own committed "
                             "docs/data/activity.json history instead of the endpoint (lower bounds)")
    parser.add_argument("--repo", default=str(REPO),
                        help="git repository to read the committed snapshots from (used by the tests)")
    args = parser.parse_args()
    out = pathlib.Path(args.out)

    if args.check:
        if not out.is_file():
            # Absent is a designed state, not a failure: the panel draws no chart without a series.
            # A *present* file is held to the endpoint's standard below.
            print(f"{out} is absent — the panel will render no chart until the first sync")
            return 0
        try:
            validate(json.loads(out.read_text(encoding="utf-8")), where=str(out))
        except (Refused, json.JSONDecodeError) as exc:
            print(f"::error::{exc}")
            return 1
        print(f"{out} is a valid series snapshot")
        return 0

    route = urllib.parse.urljoin(args.base.rstrip("/") + "/", PATH.lstrip("/"))
    try:
        if args.from_committed_snapshots:
            print("reading git history of docs/data/activity.json "
                  "(lower bounds: the last committed snapshot of each day)")
            snap = snapshot_from_committed(args.days, repo=pathlib.Path(args.repo))
        else:
            read_url = f"{route}?{urllib.parse.urlencode({'days': args.days})}"
            print(f"reading {read_url}")
            snap = snapshot_from(fetch(read_url), source=route)
    except Refused as exc:
        # The previous file is deliberately left alone: a failed fetch is not a quiet week.
        print(f"::error::refusing to write a series snapshot — {exc}")
        print(f"  {out} is unchanged (last window: "
              f"{(json.loads(out.read_text()).get('window') if out.is_file() else 'absent')})")
        return 1

    if out.is_file() and not args.force:
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = None
        if isinstance(previous, dict):
            try:
                if material(validate(previous, where=str(out))) == material(snap):
                    print(f"no material change ({snap['window']}) — nothing to write")
                    return 0
            except Refused as exc:
                # A committed file that no longer validates is worth replacing rather than keeping.
                print(f"  replacing an invalid committed file ({exc})")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                   encoding="utf-8")
    first, last = snap["series"][0], snap["series"][-1]
    print(f"wrote {out}: {snap['window']['from']}..{snap['window']['to']} "
          f"({len(snap['series'])} days, first total={first['total']}, last total={last['total']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
