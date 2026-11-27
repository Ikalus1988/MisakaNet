#!/usr/bin/env python3
"""What the plugin is actually doing in the market — one command.

Two sources, and they answer different questions:

* **The marketplace numbers** (`下载` / `使用`) are the only measure of *reach*: how many
  machines installed the plugin, and how many actually used it. The client shows them on the
  发布插件 page; there is no API for them, so they are **observed and recorded** here
  (`data/cindy-plugin-market-stats.json`). Recording them per version is the point: a reach
  number without its version cannot be compared with anything.
* **The telemetry** (`search_signals` in the production ops D1) is the measure of *use*: how many
  searches, from how many distinct machines, on which plugin version. It is what shows the
  version lag (the thing the whole #5185 work is about) and it is readable by anyone with the
  Cloudflare account.

Usage
-----
    python scripts/cindy_plugin_market_stats.py                 # market history + telemetry
    python scripts/cindy_plugin_market_stats.py --market-only   # no Cloudflare access needed
    python scripts/cindy_plugin_market_stats.py --days 14

Cloudflare access: the telemetry query goes through `wrangler d1 execute` on `misakanet-ops`.
On a machine with **no wrangler login** the query fails and the script only says
"telemetry query failed" — which reads like "no data" but is authentication (2026-11-27: `wrangler
whoami` said `You are not authenticated`, while the account and the repository's own API token were
fine). Export the token instead of logging in, and run it in WSL (the checkout's `node_modules`
holds a POSIX-built wrangler):

    export CLOUDFLARE_API_TOKEN="$(cat .cache/cf_api_token)" CLOUDFLARE_ACCOUNT_ID=<account id>
    python3 scripts/cindy_plugin_market_stats.py --days 7

The account id is the one the ops D1 lives in (same value `scripts/ae_query.py` expects).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATS = REPO / "data" / "cindy-plugin-market-stats.json"
OPS_D1 = "misakanet-ops"
CONFIG = REPO / "workers" / "wrangler.toml"

TELEMETRY_SQL = (
    "SELECT version, COUNT(*) AS searches, COUNT(DISTINCT NULLIF(client_hint,'')) AS machines, "
    "MAX(created_at) AS last_seen FROM search_signals WHERE agent='cindy' "
    "AND created_at >= datetime('now','-{days} days') GROUP BY version ORDER BY searches DESC"
)


def load_market() -> list[dict]:
    if not STATS.exists():
        return []
    return json.loads(STATS.read_text(encoding="utf-8")).get("history", [])


def print_market() -> None:
    history = load_market()
    if not history:
        print("no market numbers recorded yet — add one to data/cindy-plugin-market-stats.json")
        return
    print("marketplace reach (observed on the client's 发布插件 page)")
    # `uses` is cumulative ("ever used") while `uses_7d` is a rolling window — the publish page has
    # shown both at different times (2026-11-27: "1931 downloads / 60 uses in 7 days"). They must not
    # be subtracted from each other, so each gets its own column and the delta only compares like
    # with like.
    print(f"{'date':<12}{'version':<10}{'downloads':>10}{'uses':>8}{'uses_7d':>9}{'uses/download':>16}")
    for row in history:
        downloads = int(row.get("downloads", 0))
        uses = row.get("uses")
        uses_7d = row.get("uses_7d")
        basis = uses if uses is not None else uses_7d
        ratio = f"{int(basis) / downloads:.0%}" if downloads and basis is not None else "—"
        print(
            f"{row.get('date',''):<12}{row.get('version',''):<10}{downloads:>10}"
            f"{'' if uses is None else int(uses):>8}{'' if uses_7d is None else int(uses_7d):>9}"
            f"{ratio:>16}"
        )
    if len(history) >= 2:
        last, prev = history[-1], history[-2]
        print(
            f"\nlatest change: {last.get('version')} vs {prev.get('version')}: "
            f"downloads {int(last.get('downloads', 0)) - int(prev.get('downloads', 0)):+d}"
        )
        if last.get("uses") is not None and prev.get("uses") is not None:
            print(f"cumulative uses {int(last['uses']) - int(prev['uses']):+d}")
        if last.get("uses_7d") is not None:
            print(
                f"uses in the last 7 days {int(last['uses_7d'])} "
                "(a rolling window, not comparable to the cumulative column)"
            )


def wrangler_command() -> list[str] | None:
    """A wrangler that can actually run here.

    The repository's own `node_modules` is what CI uses; on a machine where it was installed on
    POSIX it cannot run on Windows (`workerd-linux-64`), so a locally installed one is preferred
    when it works. On WSL the repository's copy is the right one.
    """
    # The repository's own copy first: it is what CI uses and it is already installed. On a
    # machine where it was installed on POSIX it fails the `--version` probe on Windows and the
    # npx fallback takes over (which downloads a native build).
    candidates = [
        [shutil.which("node") or "node", str(REPO / "node_modules" / "wrangler" / "bin" / "wrangler.js")],
        [shutil.which("npx") or "npx", "wrangler"],
    ]
    for candidate in candidates:
        if not Path(candidate[-1]).exists() and "npx" not in candidate[0]:
            continue
        try:
            done = subprocess.run(
                candidate + ["--version"], capture_output=True, text=True, timeout=90,
                env={**os.environ, "HTTPS_PROXY": os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7890")},
            )
            if done.returncode == 0:
                return candidate
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def print_telemetry(days: int) -> None:
    command = wrangler_command()
    if command is None:
        print(
            "telemetry unavailable: no wrangler that runs here "
            "(on Windows use WSL, where the repository's own copy works)"
        )
        return
    env = {**os.environ, "HTTPS_PROXY": os.environ.get("HTTPS_PROXY", "http://127.0.0.1:7890")}
    done = subprocess.run(
        command + [
            "d1", "execute", OPS_D1, "--remote", "--config", str(CONFIG),
            "--command", TELEMETRY_SQL.format(days=days),
        ],
        capture_output=True, text=True, env=env, timeout=300,
    )
    out = done.stdout or ""
    if '"error"' in out or done.returncode != 0:
        print("telemetry query failed (that is not 'no data') — see the raw output above")
        print(out[-800:], file=sys.stderr)
        return
    start = out.find("[")
    if start < 0:
        print("telemetry: no parsable output")
        return
    rows = []
    for chunk in json.loads(out[start:]):
        for row in (chunk.get("results") or []):
            rows.append(row)
    print(f"\ntelemetry · plugin searches, last {days} day(s)")
    print(f"{'version':<12}{'searches':>10}{'machines':>10}  last seen")
    for row in rows:
        print(
            f"{str(row.get('version') or '(none)'):<12}{int(row.get('searches', 0)):>10}"
            f"{int(row.get('machines', 0)):>10}  {row.get('last_seen')}"
        )
    total = sum(int(r.get("searches", 0)) for r in rows)
    stale = sum(int(r.get("searches", 0)) for r in rows if str(r.get("version") or "").startswith(("1.2", "1.3")))
    print(f"\ntotal searches {total}; on the 1.2.x/1.3.x lines {stale} ({stale / total:.0%})" if total else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7, help="telemetry window in days (default 7)")
    parser.add_argument("--market-only", action="store_true", help="skip the telemetry query")
    args = parser.parse_args(argv)
    print_market()
    if not args.market_only:
        print_telemetry(max(1, min(args.days, 90)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
