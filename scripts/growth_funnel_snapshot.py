#!/usr/bin/env python3
"""Emit the `docs/maintainer/growth-funnel.md` weekly entry from whatever is machine-readable.

`growth-funnel.md` prescribes a weekly ritual: copy a template, paste numbers in, commit. Its
Update Log has **no entries at all** — the ritual was never run once, so every figure in the page
is from the day it was written. That is not a discipline problem, it is a design problem: a weekly
task that lives only in prose does not survive a month, and this one did not survive a week.

This script does the part that can be computed, and says so for the part that cannot. It never
invents a number: a source it cannot read is emitted as a `TODO` line with the exact URL to open,
rather than a plausible-looking figure.

Sources it can read without a browser:

| metric | source |
|---|---|
| GitHub unique visitors | `GET /repos/{o}/{r}/traffic/views` (needs push access) |
| PyPI downloads | `pypistats.org/api/packages/{pkg}/recent` |
| npm downloads | `api.npmjs.org/downloads/point/last-week/{pkg}` |
| lessons in the corpus | `canonical_lessons()` — no network |
| tools the endpoint serves | `POST https://misakanet.org/mcp` `tools/list` |
| MCP calls, daily | `GET https://misakanet.org/api/activity` |

Sources it **cannot** read, and therefore marks rather than fills: Glama analytics (no API) and
GHCR pulls (needs a token the project does not expose to CI).

Usage:
    python3 scripts/growth_funnel_snapshot.py              # print the entry, do not write
    python3 scripts/growth_funnel_snapshot.py --write      # prepend it to the Update Log
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys
import urllib.request
from datetime import date, timedelta

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "maintainer" / "growth-funnel.md"
REPO = "Ikalus1988/MisakaNet"
PYPI_PKG = "misakanet"
NPM_PKG = "misakanet"
UA = "curl/8.5.0"
TIMEOUT = 30


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _gh_json(path: str):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=TIMEOUT)
    if out.returncode:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def metrics() -> dict[str, str]:
    """Every value is a string: either a measured number or an explicit TODO. Never a guess."""
    m: dict[str, str] = {}
    iso = (date.today() - timedelta(days=7)).isoformat()
    iso_end = date.today().isoformat()

    # ── machine-readable ──────────────────────────────────────────────────────
    # GitHub's traffic endpoint answers `uniques` and covers the trailing 14 days, not 7.
    traffic = _gh_json(f"/repos/{REPO}/traffic/views")
    m["GitHub views / unique visitors (14d)"] = (
        f"{traffic['count']:,} views / **{traffic['uniques']}** unique"
        if isinstance(traffic, dict) and "uniques" in traffic
        else f"TODO(manual) — `gh api /repos/{REPO}/traffic/views` needs push access")

    try:
        pypi = _get_json(f"https://pypistats.org/api/packages/{PYPI_PKG}/recent")["data"]
        m["PyPI downloads (last week)"] = f"{pypi['last_week']:,}"
        m["PyPI downloads (last month)"] = f"{pypi['last_month']:,}"
    except Exception:
        m["PyPI downloads (last week)"] = f"TODO(manual) — pypistats.org/packages/{PYPI_PKG}"

    try:
        npm = _get_json(f"https://api.npmjs.org/downloads/point/last-week/{NPM_PKG}")
        m["npm downloads (last week)"] = f"{npm['downloads']:,}  ({npm['start']} → {npm['end']})"
    except Exception:
        m["npm downloads (last week)"] = f"TODO(manual) — npmjs.com/package/{NPM_PKG}"

    # ── repo-side, no network ─────────────────────────────────────────────────
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from misakanet.lesson_index import canonical_lessons
        n = sum(1 for p in canonical_lessons(REPO_ROOT / "lessons")
                if p.name.upper() != "README.MD" and "TEMPLATE" not in p.name.upper())
        m["lessons in the corpus"] = f"**{n}**"
    except Exception:
        m["lessons in the corpus"] = "TODO — could not import `misakanet.lesson_index`"

    # ── the project's own endpoint ────────────────────────────────────────────
    try:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode()
        req = urllib.request.Request(
            "https://misakanet.org/mcp", data=body,
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
        payload = json.loads(re.search(r"^data: (.*)$", raw, re.M).group(1))
        tools = payload["result"]["tools"]
        m["tools served by misakanet.org"] = f"**{len(tools)}** — {', '.join(sorted(t['name'] for t in tools))}"
    except Exception as exc:
        m["tools served by misakanet.org"] = f"TODO(manual) — probe failed: {type(exc).__name__}"

    try:
        act = _get_json("https://misakanet.org/api/activity")
        calls = act.get("calls", {})
        m["MCP calls (daily, rolling)"] = (
            f"total **{act.get('total')}**, mcp **{calls.get('mcp')}**, "
            f"agent **{calls.get('agent')}**, crawler **{calls.get('crawler')}**, "
            f"pageview **{calls.get('pageview')}** (generated {act.get('date')})")
    except Exception:
        m["MCP calls (daily, rolling)"] = "TODO(manual) — misakanet.org/api/activity"

    # ── the ones that need a human ────────────────────────────────────────────
    m["Glama profile views / impressions / clicks / CTR / tool calls"] = (
        "TODO(manual) — Glama dashboard Analytics tab; **no API**. This is the number the whole "
        "funnel turns on and the one that cannot be automated.")
    m["GHCR pulls"] = "TODO(manual) — package Insights, needs a token the project does not expose to CI"
    return m


def render() -> str:
    m = metrics()
    todo = sum(1 for v in m.values() if v.startswith("TODO"))
    iso = (date.today() - timedelta(days=7)).isoformat()
    iso_end = date.today().isoformat()
    lines = [
        f"### {date.today().isoformat()}",
        "",
        f"Generated by `python3 scripts/growth_funnel_snapshot.py` "
        f"(window {iso} → {iso_end}). {len(m) - todo}/{len(m)} rows measured by the script; "
        f"**{todo} need a human** and are marked, not guessed.",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k, v in m.items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "**Observations** — read the numbers above before writing anything here; a row that says "
        "`TODO` is not an observation, it is an unfinished measurement.",
        "",
        "**Actions for next week** —",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true",
                    help="prepend the entry under `## Update Log` (idempotent: skips a duplicate date)")
    args = ap.parse_args()

    entry = render()
    if not args.write:
        print(entry)
        return 0

    text = DOC.read_text(encoding="utf-8")
    heading = "## Update Log"
    if heading not in text:
        print(f"{DOC} has no `{heading}` section", file=sys.stderr)
        return 1
    today = f"### {date.today().isoformat()}"
    if today in text:
        print(f"{today} already in the Update Log — nothing written")
        return 0
    head, _, tail = text.partition(heading)
    note = re.search(r"^_\(.*\)$", tail.strip(), re.M)
    DOC.write_text(f"{head}{heading}\n\n{entry}\n\n{tail.lstrip()}", encoding="utf-8")
    print(f"wrote {today} into {DOC.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
