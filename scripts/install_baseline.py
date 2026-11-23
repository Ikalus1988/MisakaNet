#!/usr/bin/env python3
"""Read the install numbers as "the baseline between releases", not as totals.

WHY THIS EXISTS (2026-11-23)
----------------------------
The only growth signal this project has is weekly npm / PyPI downloads, and it was being read as if it
measured interest. It does not. Measured on 2026-11-23 against the registry's own publish times:

* the "spike week" 11-09…11-15 (npm 666/day, PyPI 351/day) is **exactly the week with a publish every
  single day** — 3.12.2 → 3.19.0, four of them on 11-13;
* the day after a publish averages **472** downloads, other days **213** — **2.2x** for npm;
* the week after the last publish (11-18…) falls back to 115–190/day, which is what "no release" looks
  like.

Cause is mundane and needs no theory: every publish makes mirrors, scanners, plugin markets and CI
re-resolve the package. So a number that follows **publish cadence** cannot answer "is this growing".
What can: the average over **baseline days** — days that are neither a publish day nor the day after —
compared over two windows.

This script computes exactly that, and refuses to answer when a window has too few baseline days
instead of reporting a confident number from two data points. `--check` exits 1 on a drop at or beyond
the threshold, which is the shape a nightly watcher needs; it is deliberately a script and not yet a
workflow: the reading has to be trusted before it is allowed to open issues.

Usage::

    python3 scripts/install_baseline.py                 # table + verdict, npm and PyPI
    python3 scripts/install_baseline.py --json
    python3 scripts/install_baseline.py --check         # exit 1 when a baseline dropped >= 40%
    python3 scripts/install_baseline.py --check --threshold 30 --window 10

Exit codes: 0 = read (no drop, or nothing to compare), 1 = a drop at/over the threshold,
2 = could not read (network/registry failure) — which is *not* the same answer as "all fine".
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import urllib.request

NPM_RANGE = "https://api.npmjs.org/downloads/range/{start}:{end}/{package}"
NPM_DOC = "https://registry.npmjs.org/{package}"
PYPI_OVERALL = "https://pypistats.org/api/packages/{package}/overall?mirrors=false"
PYPI_JSON = "https://pypi.org/pypi/{package}/json"

#: A window with fewer baseline days than this is not averaged: with a release every day there is no
#: baseline to read, and the honest answer is "cannot judge" rather than a number from two points.
MIN_BASELINE_DAYS = 3


def classify(days: dict[str, int], publish_days: set[str]) -> dict[str, str]:
    """Label each day `release`, `after` (the day following a publish) or `baseline`."""
    labels: dict[str, str] = {}
    for day in days:
        date = _dt.date.fromisoformat(day)
        previous = (date - _dt.timedelta(days=1)).isoformat()
        if day in publish_days:
            labels[day] = "release"
        elif previous in publish_days:
            labels[day] = "after"
        else:
            labels[day] = "baseline"
    return labels


def window_average(days: dict[str, int], labels: dict[str, str],
                   start: str, end: str) -> tuple[float | None, int]:
    """Average downloads over the **baseline** days in `[start, end]`, and how many there were."""
    values = [days[d] for d in days if start <= d <= end and labels.get(d) == "baseline"]
    if len(values) < MIN_BASELINE_DAYS:
        return None, len(values)
    return sum(values) / len(values), len(values)


def drop_percent(previous: float | None, current: float | None) -> float | None:
    """How far the current baseline fell below the previous one, as a positive percent."""
    if not previous or current is None:
        return None
    return (previous - current) / previous * 100.0


def read_days(days: dict[str, int], publish_days: set[str], *,
              window: int, end: str) -> dict:
    """Both windows for one channel. `end` is the last day of the *current* window."""
    labels = classify(days, publish_days)
    end_date = _dt.date.fromisoformat(end)
    cur_start = (end_date - _dt.timedelta(days=window - 1)).isoformat()
    prev_end = (end_date - _dt.timedelta(days=window)).isoformat()
    prev_start = (end_date - _dt.timedelta(days=2 * window - 1)).isoformat()

    current, cur_n = window_average(days, labels, cur_start, end)
    previous, prev_n = window_average(days, labels, prev_start, prev_end)
    return {
        "current": {"start": cur_start, "end": end, "average": current, "baseline_days": cur_n},
        "previous": {"start": prev_start, "end": prev_end, "average": previous, "baseline_days": prev_n},
        "drop_percent": drop_percent(previous, current),
        "labels": labels,
    }


def verdict(result: dict, threshold: float) -> tuple[str, str]:
    """`ok` / `dropped` / `cannot-judge`, with the reason."""
    current = result["current"]
    previous = result["previous"]
    if previous["average"] is None or current["average"] is None:
        return "cannot-judge", (
            f"too few baseline days (previous {previous['baseline_days']}, "
            f"current {current['baseline_days']}, need {MIN_BASELINE_DAYS}) — "
            "a release-heavy window has no baseline to read")
    drop = result["drop_percent"]
    if drop is None:
        return "cannot-judge", "no previous average to compare against"
    if drop >= threshold:
        return "dropped", (f"baseline fell {drop:.0f}% "
                           f"({previous['average']:.0f} → {current['average']:.0f}/day)")
    # Reported as a signed **change** rather than a drop: `drop_percent` is negative on a rise, and
    # "(-50%)" next to the word drop reads as a halving when it is a doubling.
    return "ok", (f"baseline {current['average']:.0f}/day against {previous['average']:.0f} "
                  f"({-drop:+.0f}%)")


# ── the two registries ──────────────────────────────────────────────────────────────────────────

def _get(url: str, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "misakanet-install-baseline"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — fixed hosts
        return json.loads(response.read().decode("utf-8"))


def npm_series(package: str, start: str, end: str) -> tuple[dict[str, int], set[str]]:
    payload = _get(NPM_RANGE.format(start=start, end=end, package=package))
    days = {row["day"]: int(row["downloads"]) for row in payload.get("downloads", [])}
    doc = _get(NPM_DOC.format(package=package))
    times = doc.get("time") or {}
    publishes = {stamp[:10] for version, stamp in times.items()
                 if version not in ("created", "modified") and isinstance(stamp, str)}
    return days, publishes


def pypi_series(package: str) -> tuple[dict[str, int], set[str]]:
    payload = _get(PYPI_OVERALL.format(package=package))
    days: dict[str, int] = {}
    for row in payload.get("data", []):
        if row.get("category") == "without_mirrors":
            days[row["date"]] = days.get(row["date"], 0) + int(row["downloads"])
    doc = _get(PYPI_JSON.format(package=package))
    publishes: set[str] = set()
    for files in (doc.get("releases") or {}).values():
        for f in files or []:
            stamp = f.get("upload_time_iso_8601") or f.get("upload_time") or ""
            if stamp:
                publishes.add(stamp[:10])
                break
    return days, publishes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--window", type=int, default=7, help="days per window (default 7)")
    parser.add_argument("--threshold", type=float, default=40.0,
                        help="drop percent that counts as a drop (default 40)")
    parser.add_argument("--end", default=None, help="last day of the current window (default yesterday)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="exit 1 on a drop at/over the threshold")
    args = parser.parse_args(argv)

    end = args.end or (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
    start = (_dt.date.fromisoformat(end) - _dt.timedelta(days=2 * args.window - 1)).isoformat()

    report: dict[str, dict] = {}
    worst = "ok"
    for channel, package in (("npm", "misakanet"), ("pypi", "misakanet")):
        try:
            days, publishes = (npm_series(package, start, end) if channel == "npm"
                               else pypi_series(package))
        except Exception as error:  # noqa: BLE001 — the exit code carries the distinction
            print(f"{channel}: cannot read ({type(error).__name__}: {error})", file=sys.stderr)
            return 2
        result = read_days(days, publishes, window=args.window, end=end)
        state, reason = verdict(result, args.threshold)
        if state == "dropped":
            worst = "dropped"
        report[channel] = {
            "verdict": state,
            "reason": reason,
            "current": result["current"],
            "previous": result["previous"],
            "drop_percent": result["drop_percent"],
            "release_days_in_window": sorted(d for d, l in result["labels"].items()
                                             if l == "release" and d >= result["current"]["start"]),
        }

    if args.json:
        print(json.dumps({"end": end, "window": args.window, "threshold": args.threshold,
                          "channels": report}, ensure_ascii=False, indent=1))
    else:
        print(f"install baseline — window {args.window}d ending {end}\n")
        for channel, row in report.items():
            print(f"  {channel:4s} {row['verdict']:12s} {row['reason']}")
            print(f"        current {row['current']['start']}…{row['current']['end']}: "
                  f"{row['current']['baseline_days']} baseline day(s)"
                  + (f", releases {', '.join(row['release_days_in_window'])}"
                     if row["release_days_in_window"] else ", no release"))
        print("\nA release day and the day after it are excluded: they measure the package being "
              "re-resolved, not the package being wanted.")

    if args.check and worst == "dropped":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
