#!/usr/bin/env python3
"""MHS Watch — Anthropic Model Hardware Standard ecosystem monitor.

Scans GitHub for early-adapter activity related to Anthropic's Model Hardware
Standard (MHS, announced 2026-08-27). Alerts on commits / PRs / issues /
discussions matching MHS-related keywords across official launch partners,
Anthropic itself, and adjacent ecosystems (MCP, agent governance).

Usage:
    python3 scripts/mhs_watch.py once                    # one-shot scan
    python3 scripts/mhs_watch.py daemon --interval 3600  # loop, every hour
    python3 scripts/mhs_watch.py status                  # last scan summary
    python3 scripts/mhs_watch.py tail                    # tail hits log

State & logs (created on first run; lives in repo's gitignored .cache/):
    .cache/mhs-watch/state.json            # last-seen ids per (repo, kind)
    .cache/mhs-watch/hits.jsonl            # append-only match log
    .cache/mhs-watch/watch.log             # scan history

Environment:
    MHS_WATCH_HOME         override state directory (default: <repo>/.cache/mhs-watch)
    MHS_WATCH_GITHUB_TOKEN GitHub PAT (optional, bumps rate limit 60/hr -> 5000/hr)
    MHS_WATCH_WEBHOOK_URL  POST target on each hit (Slack incoming / Discord / etc.)
    MHS_WATCH_CONFIG       path to config json (default: scripts/mhs_watch_config.json)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

GITHUB_API = "https://api.github.com"

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO / "scripts" / "mhs_watch_config.json"

# State lives inside the repo's gitignored .cache/ so we don't need write access
# to $HOME. Override with MHS_WATCH_HOME if you want a different location.
STATE_DIR = Path(
    os.environ.get("MHS_WATCH_HOME", str(REPO / ".cache" / "mhs-watch"))
)
STATE_FILE = STATE_DIR / "state.json"
HITS_FILE = STATE_DIR / "hits.jsonl"
LOG_FILE = STATE_DIR / "watch.log"

# ---- HTTP helpers ---------------------------------------------------------

def gh_headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mhs-watch/0.1 (+MisakaNet)",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    tok = os.environ.get("MHS_WATCH_GITHUB_TOKEN", "").strip()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def gh_get(path: str, params: dict | None = None, retries: int = 1) -> tuple[int, dict, dict]:
    """GET a GitHub API endpoint. Returns (status, headers, body-as-dict-or-raw).

    On network/5xx errors, retries once with backoff. Returns (-1, {}, {}) on
    unrecoverable failure so callers can skip the repo gracefully.
    """
    url = f"{GITHUB_API}{path}"
    if params:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if qs:
            url = f"{url}?{qs}"
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=gh_headers())
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                try:
                    parsed = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    parsed = {"_raw": body[:500]}
                return resp.status, hdrs, parsed
        except urllib.error.HTTPError as e:
            hdrs = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {"_raw": body[:500]}
            return e.code, hdrs, parsed
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 + attempt * 2)
                continue
            return -1, {}, {"_error": str(e)}
    return -1, {}, {"_error": str(last_err) if last_err else "unknown"}


# ---- State persistence ----------------------------------------------------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"scans": [], "last_seen": {}, "totals": {"hits": 0, "scans": 0}}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"scans": [], "last_seen": {}, "totals": {"hits": 0, "scans": 0}}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(STATE_FILE)


def append_hit(hit: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with HITS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(hit, ensure_ascii=False, sort_keys=True) + "\n")


def log_line(level: str, msg: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{ts} [{level}] {msg}\n")
    if level in ("ERROR", "WARN"):
        print(f"[{level}] {msg}", file=sys.stderr)
    elif level == "INFO" and os.environ.get("MHS_WATCH_VERBOSE"):
        print(f"[{level}] {msg}", file=sys.stderr)


# ---- Keyword matching -----------------------------------------------------

KEYWORD_RE_CACHE: dict[str, re.Pattern[str]] = {}


def keyword_patterns(keywords: list[str]) -> list[re.Pattern[str]]:
    pats: list[re.Pattern[str]] = []
    for kw in keywords:
        if kw in KEYWORD_RE_CACHE:
            pats.append(KEYWORD_RE_CACHE[kw])
            continue
        # word-boundary-ish: allow @-prefix, hyphens, and case-insensitive substring.
        pat = re.compile(re.escape(kw), re.IGNORECASE)
        KEYWORD_RE_CACHE[kw] = pat
        pats.append(pat)
    return pats


def score_text(text: str, keywords: list[str], patterns: list[re.Pattern[str]]) -> tuple[list[str], int]:
    if not text:
        return [], 0
    matched: list[str] = []
    for kw, pat in zip(keywords, patterns):
        if pat.search(text):
            matched.append(kw)
    return matched, len(matched)


def snippet(text: str, limit: int = 240) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()
    return t[:limit] + ("…" if len(t) > limit else "")


# ---- GitHub scanners ------------------------------------------------------

def list_commits(repo: str, since_iso: str) -> list[dict]:
    status, hdrs, body = gh_get(
        f"/repos/{repo}/commits",
        params={"since": since_iso, "per_page": 50},
    )
    if status != 200 or not isinstance(body, list):
        if status == 404:
            log_line("WARN", f"repo not found or private: {repo}")
        elif status == 403:
            remaining = hdrs.get("x-ratelimit-remaining", "?")
            reset = hdrs.get("x-ratelimit-reset", "?")
            log_line("WARN", f"rate limited (remaining={remaining}, reset={reset}); consider MHS_WATCH_GITHUB_TOKEN")
        elif status != -1:
            log_line("WARN", f"commits http {status} for {repo}")
        return []
    return body


def list_pulls(repo: str, since_iso: str) -> list[dict]:
    # PRs since cutoff: sort=updated gives us recently-touched PRs; filter by created.
    status, hdrs, body = gh_get(
        f"/repos/{repo}/pulls",
        params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 50},
    )
    if status != 200 or not isinstance(body, list):
        if status == 404:
            log_line("WARN", f"repo not found or private: {repo}")
        return []
    cutoff = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    return [pr for pr in body
            if pr.get("created_at") and
               datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")) >= cutoff]


def list_issues(repo: str, since_iso: str) -> list[dict]:
    status, hdrs, body = gh_get(
        f"/repos/{repo}/issues",
        params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 50, "since": since_iso},
    )
    if status != 200 or not isinstance(body, list):
        if status == 404:
            log_line("WARN", f"repo not found or private: {repo}")
        return []
    # exclude PRs (GitHub returns PRs in /issues)
    return [iss for iss in body if "pull_request" not in iss]


# ---- Scan orchestration ---------------------------------------------------

def scan_once(config: dict, state: dict) -> dict:
    """One full scan pass. Returns a scan summary dict."""
    scan_id = uuid.uuid4().hex[:12]
    ts = datetime.now(timezone.utc)
    iso_now = ts.isoformat(timespec="seconds").replace("+00:00", "Z")
    lookback_days = int(config.get("lookback_days", 14))
    since_iso = (ts - timedelta(days=lookback_days)).isoformat(timespec="seconds").replace("+00:00", "Z")

    keywords = [k for k in config.get("keywords", []) if k]
    patterns = keyword_patterns(keywords)
    min_conf = int(config.get("min_confidence", 1))
    kinds = set(config.get("kinds", ["commits", "pulls", "issues", "discussions"]))
    repos = [r for r in config.get("repos", []) if r]

    summary = {
        "scan_id": scan_id,
        "ts": iso_now,
        "since": since_iso,
        "repos_scanned": 0,
        "repos_skipped": 0,
        "items_seen": {"commits": 0, "pulls": 0, "issues": 0},
        "hits": 0,
        "errors": 0,
        "rate_limit_remaining": None,
    }

    new_hits: list[dict] = []
    SEEN_CAP = int(config.get("seen_cap", 2000))  # ids per (repo, kind)

    for repo in repos:
        # Migrate old single-id state ("commits": "<sha>") to seen-set on first run.
        last_seen_repo = state["last_seen"].get(repo, {})
        for kind in ("commits", "pulls", "issues"):
            v = last_seen_repo.get(kind)
            if isinstance(v, str):
                last_seen_repo[kind] = {"seen": [v]} if v else {"seen": []}
            elif "seen" not in last_seen_repo.get(kind, {}):
                last_seen_repo[kind] = {"seen": []}
            last_seen_repo[kind]["seen"] = last_seen_repo[kind]["seen"][-SEEN_CAP:]

        # commits
        if "commits" in kinds:
            items = list_commits(repo, since_iso)
            summary["items_seen"]["commits"] += len(items)
            seen_commits = set(last_seen_repo["commits"]["seen"])
            for it in items:
                sha = it.get("sha", "")
                if not sha or sha in seen_commits:
                    continue
                msg = it.get("commit", {}).get("message", "") or ""
                title = msg.split("\n", 1)[0]
                body = msg
                matched, conf = score_text(f"{title}\n{body}", keywords, patterns)
                if conf >= min_conf:
                    new_hits.append({
                        "ts": iso_now,
                        "scan_id": scan_id,
                        "repo": repo,
                        "kind": "commit",
                        "id": sha,
                        "title": title,
                        "url": it.get("html_url", ""),
                        "author": (it.get("author") or {}).get("login") or (it.get("commit", {}).get("author") or {}).get("name", ""),
                        "created_at": it.get("commit", {}).get("author", {}).get("date", ""),
                        "matched_keywords": matched,
                        "confidence": conf,
                        "snippet": snippet(body),
                    })
                seen_commits.add(sha)
            last_seen_repo["commits"]["seen"] = list(seen_commits)[-SEEN_CAP:]

        # pulls
        if "pulls" in kinds:
            items = list_pulls(repo, since_iso)
            summary["items_seen"]["pulls"] += len(items)
            seen_pulls = set(last_seen_repo["pulls"]["seen"])
            for pr in items:
                pid = str(pr.get("id", ""))
                if not pid or pid in seen_pulls:
                    continue
                title = pr.get("title", "") or ""
                body = pr.get("body", "") or ""
                matched, conf = score_text(f"{title}\n{body}", keywords, patterns)
                if conf >= min_conf:
                    new_hits.append({
                        "ts": iso_now,
                        "scan_id": scan_id,
                        "repo": repo,
                        "kind": "pull_request",
                        "id": pid,
                        "number": pr.get("number"),
                        "title": title,
                        "url": pr.get("html_url", ""),
                        "author": (pr.get("user") or {}).get("login", ""),
                        "created_at": pr.get("created_at", ""),
                        "matched_keywords": matched,
                        "confidence": conf,
                        "snippet": snippet(body),
                    })
                seen_pulls.add(pid)
            last_seen_repo["pulls"]["seen"] = list(seen_pulls)[-SEEN_CAP:]

        # issues (excludes PRs)
        if "issues" in kinds:
            items = list_issues(repo, since_iso)
            summary["items_seen"]["issues"] += len(items)
            seen_issues = set(last_seen_repo["issues"]["seen"])
            for iss in items:
                iid = str(iss.get("id", ""))
                if not iid or iid in seen_issues:
                    continue
                title = iss.get("title", "") or ""
                body = iss.get("body", "") or ""
                matched, conf = score_text(f"{title}\n{body}", keywords, patterns)
                if conf >= min_conf:
                    new_hits.append({
                        "ts": iso_now,
                        "scan_id": scan_id,
                        "repo": repo,
                        "kind": "issue",
                        "id": iid,
                        "number": iss.get("number"),
                        "title": title,
                        "url": iss.get("html_url", ""),
                        "author": (iss.get("user") or {}).get("login", ""),
                        "created_at": iss.get("created_at", ""),
                        "matched_keywords": matched,
                        "confidence": conf,
                        "snippet": snippet(body),
                    })
                seen_issues.add(iid)
            last_seen_repo["issues"]["seen"] = list(seen_issues)[-SEEN_CAP:]

        # discussions: GitHub requires GraphQL for first-class listing.
        # We approximate via the Discussions tab HTML scrape — disabled for now.
        if "discussions" in kinds:
            log_line("INFO", "discussions kind requested but GraphQL scanner not implemented; skipping")

        state["last_seen"][repo] = last_seen_repo
        summary["repos_scanned"] += 1

    # write hits
    for h in new_hits:
        append_hit(h)
        print(json.dumps(h, ensure_ascii=False, sort_keys=True))

    summary["hits"] = len(new_hits)
    state["scans"].append({
        "scan_id": scan_id,
        "ts": iso_now,
        "hits": len(new_hits),
        "items": summary["items_seen"],
        "repos_scanned": summary["repos_scanned"],
    })
    # cap scan history to last 200
    state["scans"] = state["scans"][-200:]
    state["totals"]["hits"] = state["totals"].get("hits", 0) + len(new_hits)
    state["totals"]["scans"] = state["totals"].get("scans", 0) + 1

    save_state(state)

    # webhook fan-out
    webhook = os.environ.get("MHS_WATCH_WEBHOOK_URL", "").strip()
    if webhook and new_hits:
        try:
            payload = {"scan_id": scan_id, "ts": iso_now, "hits": new_hits}
            req = urllib.request.Request(
                webhook,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            log_line("WARN", f"webhook post failed: {e}")

    return summary


# ---- Config loading -------------------------------------------------------

def load_config(path: Path) -> dict:
    if not path.exists():
        log_line("ERROR", f"config not found: {path}")
        sys.exit(2)
    try:
        cfg = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        log_line("ERROR", f"config invalid JSON: {e}")
        sys.exit(2)
    if "repos" not in cfg or not isinstance(cfg["repos"], list):
        log_line("ERROR", "config: 'repos' must be a list of 'owner/name' strings")
        sys.exit(2)
    if "keywords" not in cfg or not isinstance(cfg["keywords"], list):
        log_line("ERROR", "config: 'keywords' must be a list of strings")
        sys.exit(2)
    return cfg


# ---- Subcommands ----------------------------------------------------------

def cmd_once(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    state = load_state()
    summary = scan_once(cfg, state)
    print(json.dumps({"summary": summary, "total_hits": state["totals"]["hits"]},
                     ensure_ascii=False, indent=2), file=sys.stderr)
    return 0 if summary["errors"] == 0 else 1


def cmd_daemon(args: argparse.Namespace) -> int:
    cfg = load_config(Path(args.config))
    interval = max(60, int(args.interval))
    running = {"flag": True}

    def _stop(signum, frame):
        running["flag"] = False
        log_line("INFO", f"signal {signum} received; exiting after current scan")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log_line("INFO", f"daemon start, interval={interval}s, state={STATE_DIR}")
    while running["flag"]:
        state = load_state()
        try:
            summary = scan_once(cfg, state)
            log_line("INFO",
                     f"scan {summary['scan_id']}: "
                     f"{summary['repos_scanned']} repos, "
                     f"{summary['items_seen']} items, "
                     f"{summary['hits']} hits")
        except Exception as e:
            log_line("ERROR", f"scan crashed: {e}")
        # sleep in 1s slices so SIGTERM is responsive
        for _ in range(interval):
            if not running["flag"]:
                break
            time.sleep(1)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state()
    print(json.dumps({
        "state_dir": str(STATE_DIR),
        "hits_file": str(HITS_FILE),
        "totals": state.get("totals", {}),
        "last_5_scans": state.get("scans", [])[-5:],
        "tracked_repos": sorted(state.get("last_seen", {}).keys()),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    if not HITS_FILE.exists():
        print("(no hits yet)", file=sys.stderr)
        return 0
    n = int(args.n)
    lines = HITS_FILE.read_text(errors="replace").splitlines()[-n:]
    for ln in lines:
        try:
            obj = json.loads(ln)
            print(f"[{obj.get('ts','')}] {obj.get('repo','')}/{obj.get('kind','')} "
                  f"(conf={obj.get('confidence','?')}, kws={obj.get('matched_keywords',[])})")
            print(f"  {obj.get('title','')}")
            print(f"  {obj.get('url','')}")
            if obj.get("snippet"):
                print(f"  › {obj['snippet'][:160]}")
        except json.JSONDecodeError:
            print(ln)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "MHS Watch")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("once", help="single scan and exit")
    p1.add_argument("--config", default=os.environ.get("MHS_WATCH_CONFIG", str(DEFAULT_CONFIG_PATH)))
    p1.set_defaults(func=cmd_once)

    p2 = sub.add_parser("daemon", help="loop forever, scan every N seconds")
    p2.add_argument("--interval", type=int, default=3600,
                    help="seconds between scans (default 3600 = 1h, min 60)")
    p2.add_argument("--config", default=os.environ.get("MHS_WATCH_CONFIG", str(DEFAULT_CONFIG_PATH)))
    p2.set_defaults(func=cmd_daemon)

    p3 = sub.add_parser("status", help="show last scan summary")
    p3.set_defaults(func=cmd_status)

    p4 = sub.add_parser("tail", help="tail recent hits")
    p4.add_argument("-n", default=20)
    p4.set_defaults(func=cmd_tail)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())