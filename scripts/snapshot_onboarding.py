#!/usr/bin/env python3
"""Publish the onboarding funnel weekly: installs in, agent calls out.

**Why this exists instead of a download count.** Measured 2026-09-30/10-01, the two npm numbers are not
comparable and not human: `misakanet` (the plugin/bundle) is re-fetched on every install and update, while
`@misaka-net/misakanet-setup` is run once per machine and then served from npx's cache — and its "monthly
1,814" was one week (09-14: 1,661) that no workflow of ours produced. GitHub's own 14-day traffic says the
same thing from another angle: **3,079 unique cloners against 689 unique visitors**, i.e. machines clone 4.5×
more often than people look, while the MCP endpoint answers ~7,600 calls a day. Downloads measure one moment
of a pipeline; what matters is whether an install becomes an agent that actually searches.

So this writes **one snapshot** with the three legs side by side:

* `downloads` — npm weekly, per package (the funnel's top);
* `activity` — today's `mcp` / `agent` / `crawler` / `pageview` counts from the site's own projection
  (the funnel's bottom: is anyone calling?);
* `traffic` — GitHub's 14-day clones/views (context: how much of the clone number is even human).

and one derived number, `mcp_per_weekly_install`: agent calls per week divided by installer downloads per
week. It is a **proxy, not a conversion rate** (both terms are noisy: npx caching suppresses the
denominator, and one agent makes many calls), which is why the badge shows the raw pair and this file keeps
the arithmetic.

**Publishing rule** (the same one `badges/install.json` follows): a number that could not be measured is not
published. If npm or the activity projection is unreachable, nothing is written and the run says why.

Usage:
    python3 scripts/snapshot_onboarding.py --out /tmp/badges/onboarding.json
    python3 scripts/snapshot_onboarding.py --out -            # print only, write nothing
    python3 scripts/snapshot_onboarding.py --out - --no-traffic
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PACKAGES = ("misakanet", "@misaka-net/misakanet-setup")
DOWNLOAD_API = "https://api.npmjs.org/downloads/point/last-week/{pkg}"
TRAFFIC_API = "https://api.github.com/repos/{repo}/traffic/{kind}?per_page=14"
DEFAULT_OUT = Path("badges/onboarding.json")
REPO_SLUG = "Ikalus1988/MisakaNet"


def _get_json(url: str, token: str | None = None, timeout: int = 30) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": "misakanet-onboarding-snapshot"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        return json.load(urllib.request.urlopen(request, timeout=timeout))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None


def npm_week(pkg: str, *, fetch=_get_json) -> int | None:
    """Downloads in the last completed week (npm's own window), or None when it cannot be measured."""
    payload = fetch(DOWNLOAD_API.format(pkg=pkg.replace("/", "%2F")))
    value = (payload or {}).get("downloads")
    return value if isinstance(value, int) else None


def activity_counts(path: Path | None = None, *, fetch=_get_json) -> dict | None:
    """Today's call counts, from the repository's projection (rewritten every three hours) or the live one."""
    local = Path(path or Path(__file__).resolve().parent.parent / "docs" / "data" / "activity.json")
    payload = None
    if local.is_file():
        try:
            payload = json.loads(local.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
    if payload is None:
        payload = fetch("https://misakanet.org/api/activity")
    calls = ((payload or {}).get("calls")) or {}
    if not isinstance(calls, dict) or not isinstance(calls.get("mcp"), int):
        return None
    return {"date": payload.get("date"), "total": payload.get("total"),
            "calls": {k: v for k, v in calls.items() if isinstance(v, int)}}


def github_traffic(*, fetch=_get_json, token: str | None = None) -> dict | None:
    """14-day clones/views — context for how much of the install traffic is machines."""
    clones = fetch(TRAFFIC_API.format(repo=REPO_SLUG, kind="clones"), token)
    views = fetch(TRAFFIC_API.format(repo=REPO_SLUG, kind="views"), token)
    if not clones or not views:
        return None
    return {
        "window_days": len(clones.get("clones") or []),
        "clones": clones.get("count"), "unique_cloners": clones.get("uniques"),
        "views": views.get("count"), "unique_visitors": views.get("uniques"),
    }


def compose(downloads: dict, activity: dict, traffic: dict | None, *, now: str | None = None) -> dict:
    """The badge (shields-shaped) plus the measured detail, in one file. Shields ignores extra fields."""
    setup = downloads.get("@misaka-net/misakanet-setup")
    plugin = downloads.get("misakanet")
    mcp_day = (activity.get("calls") or {}).get("mcp")
    payload = {
        "schemaVersion": 1,
        "label": "onboarding",
        "message": f"setup {setup}/wk · MCP {round((mcp_day or 0) / 100) / 10}k/day"
        if isinstance(setup, int) and isinstance(mcp_day, int) else "measured weekly",
        "color": "blue",
        "generated_at": now or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {"downloads": "last-week", "activity": activity.get("date"), "traffic": "14d"},
        "downloads": {name: value for name, value in
                      (("misakanet", plugin), ("misakanet-setup", setup))},
        "activity": activity,
        "traffic": traffic,
    }
    if isinstance(setup, int) and setup > 0 and isinstance(mcp_day, int):
        payload["mcp_per_weekly_install"] = round(mcp_day * 7 / setup, 1)
        payload["mcp_per_weekly_install_note"] = (
            "proxy, not a conversion rate: npx caching depresses the denominator and one agent makes many "
            "calls. Read it as a trend, never as a score."
        )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="where to write the snapshot (`-` prints it)")
    parser.add_argument("--no-traffic", action="store_true",
                        help="skip the GitHub traffic fetch (no token available)")
    parser.add_argument("--activity", type=Path, help="read the activity projection from this file")
    args = parser.parse_args(argv)

    downloads = {name: npm_week(name) for name in PACKAGES}
    missing = sorted(name for name, value in downloads.items() if value is None)
    activity = activity_counts(args.activity)
    problems = []
    if missing:
        problems.append(f"npm did not report weekly downloads for: {', '.join(missing)}")
    if activity is None:
        problems.append("the activity projection carries no `calls.mcp` count")
    if problems:
        # Absent evidence is not a pass, and it is not a zero either: publish nothing and say why.
        print("not publishing an onboarding snapshot:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    traffic = None if args.no_traffic else github_traffic(token=token)
    payload = compose(downloads, activity, traffic)

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if str(args.out) == "-":
        print(text, end="")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}: {payload['message']}"
          + ("" if traffic else " (no traffic leg: no token or the API refused)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
