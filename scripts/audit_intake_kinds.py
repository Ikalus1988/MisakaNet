#!/usr/bin/env python3
"""Audit historical intake issues: question vs lesson discrimination (#1396).

For every GitHub intake issue (labels ``intake``/``mcp-intake``), compare the
kind recorded in the issue body (``**Kind:**``) with what the current
question detector (:func:`scripts.intake_kind.infer_intake_kind`) would decide
from the submitted problem text alone.

Outputs:
- JSONL rows per issue (``--out``)
- flagged recovery candidates: issues whose content reads as a question but
  were routed as ``missing_lesson`` and auto-rejected (dead end before the
  #1396 routing fix), or issues with an explicit ``kind=question`` that were
  auto-rejected by the pre-fix lesson auto-review

Usage:
    python3 scripts/audit_intake_kinds.py --labels mcp-intake --out /tmp/intake_audit.jsonl
    python3 scripts/audit_intake_kinds.py --labels auto-rejected --state open --summary

Auth: GH_TOKEN / GITHUB_TOKEN env, else ~/.git-credentials (Ikalus1988).
Read-only — never modifies issues.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "Ikalus1988/MisakaNet"
API = f"https://api.github.com/repos/{REPO}"

OPIRE_RE = re.compile(r"<details>[\s\S]*?</details>", re.I)


def _token() -> str:
    for env in ("GH_TOKEN", "GITHUB_TOKEN"):
        t = os.environ.get(env, "").strip()
        if t:
            return t
    cred = Path.home() / ".git-credentials"
    if cred.exists():
        m = re.match(r"https://[^:]+:([^@]+)@", cred.read_text(errors="replace").strip())
        if m:
            return m.group(1)
    return ""


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "misakanet-audit",
    }


def api_get(path: str, retries: int = 3) -> dict | list:
    last = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(API + path, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, http.client.IncompleteRead) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code < 500:
                print(f"  !! API {e.code} for {path}: {e.read()[:200]}", file=sys.stderr)
                raise
            print(f"  !! attempt {attempt} failed for {path}: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise last


def fetch_issues(labels: list[str], state: str, limit: int) -> list[dict]:
    """Paginate /issues by label combo (union across labels, skip PRs)."""
    seen: dict[int, dict] = {}
    for label in labels:
        page = 1
        while True:
            q = urllib.parse.urlencode({
                "state": state,
                "labels": label,
                "per_page": 100,
                "page": page,
            })
            data = api_get(f"/issues?{q}")
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if "pull_request" in item:
                    continue
                seen[item["number"]] = item
            if len(data) < 100 or (limit and len(seen) >= limit):
                break
            page += 1
            if limit and len(seen) >= limit:
                break
        if limit and len(seen) >= limit:
            break
    issues = list(seen.values())
    issues.sort(key=lambda i: i["number"])
    return issues[:limit] if limit else issues


def parse_intake(issue: dict) -> dict:
    body = issue.get("body") or ""
    title = issue.get("title") or ""
    kind_m = re.search(r"\*\*Kind:\*\*\s*([^\n]+)", body, re.I)
    kind_body = kind_m.group(1).strip().lower() if kind_m else ""

    # Submitter-authored problem text. Cut at issue-footer markers so the
    # Opire/details boilerplate ("what does it mean?", "add rewards",
    # "documentation") never reaches the detector — same pollution class that
    # broke the old triage keyword classifier on #1396.
    def _cut_footer(text: str) -> str:
        text = OPIRE_RE.sub(" ", text)
        # horizontal rule that precedes "_Submitted via remote MCP ..."
        text = re.sub(r"\n[-_]{3,}\n.*$", "", text, flags=re.S)
        # any standalone "_Submitted via ..." / "_Dedup hash: ..." trailer
        text = re.sub(r"(?m)^_?(Submitted via|Dedup hash)[^\n]*$", "", text)
        return text.strip()

    problem = ""
    prob_m = re.search(r"##\s+Problem\s*\n(.*?)(?=\n##|\Z)", body, re.S)
    if prob_m:
        problem = _cut_footer(prob_m.group(1))
    if not problem:
        cleaned = _cut_footer(body)
        cleaned = re.sub(r"^\*\*(Kind|Source|Dedup):\*\*.*$", "", cleaned, flags=re.M)
        cleaned = re.sub(r"^[-_]{3,}$", "", cleaned, flags=re.M)
        problem = "\n".join(l for l in cleaned.splitlines() if l.strip())[:2000]
    return {"title": title, "kind_body": kind_body, "problem": problem[:2000]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--labels", default="mcp-intake",
                    help="comma-separated labels (default: mcp-intake)")
    ap.add_argument("--state", default="all", choices=["open", "closed", "all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="", help="JSONL output path (default: stdout)")
    ap.add_argument("--summary", action="store_true", help="print summary table only")
    args = ap.parse_args()

    from scripts.intake_kind import infer_intake_kind  # local import: repo path

    labels = [l.strip() for l in args.labels.split(",") if l.strip()]
    issues = fetch_issues(labels, args.state, args.limit)
    print(f"fetched {len(issues)} issues (labels={labels}, state={args.state})", file=sys.stderr)

    rows = []
    for issue in issues:
        parsed = parse_intake(issue)
        kind_det, auto = infer_intake_kind(
            kind=parsed["kind_body"], problem=parsed["problem"],
        )
        label_names = sorted(l["name"] for l in issue.get("labels", []))
        row = {
            "number": issue["number"],
            "title": parsed["title"][:100],
            "state": issue["state"],
            "labels": label_names,
            "kind_body": parsed["kind_body"] or "none",
            "kind_detected": kind_det,
            "auto_detected": auto,
            "problem_preview": parsed["problem"].replace("\n", " ")[:140],
        }
        rows.append(row)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"wrote {len(rows)} rows -> {args.out}")

    if args.summary or not args.out:
        print(f"\n{'#':>4} {'state':<6} {'kind_body':<20} {'detected':<14} {'auto':<5} labels")
        for r in rows:
            auto = "Y" if r["auto_detected"] else ""
            print(f"{r['number']:>4} {r['state']:<6} {r['kind_body']:<20} "
                  f"{r['kind_detected']:<14} {auto:<5} {','.join(x for x in r['labels'] if x in ('auto-rejected','needs-salvage','question','type:question','test','needs-human-review','pending-review'))}")

    # ── flagged recovery candidates ──
    flagged = []
    for r in rows:
        ln = set(r["labels"])
        rejected = "auto-rejected" in ln
        # 1) content reads as a question but was rejected as a lesson
        if r["auto_detected"] and rejected:
            flagged.append((r, "question-content-auto-rejected"))
        # 2) explicit kind=question that was auto-rejected pre-fix
        elif r["kind_body"] == "question" and rejected:
            flagged.append((r, "explicit-question-auto-rejected"))
        # 3) explicit kind=question missing question labels (never routed)
        elif r["kind_body"] == "question" and not ({"question"} & ln):
            flagged.append((r, "explicit-question-unlabeled"))
    if flagged:
        print(f"\n== {len(flagged)} flagged recovery candidates ==")
        for r, why in flagged:
            print(f"#{r['number']} [{why}] {r['state']} {r['title']}")
            print(f"    problem: {r['problem_preview']}")
    else:
        print("\n== no flagged recovery candidates ==")

    # ── cross-check: explicit kinds that should NOT flip ──
    flipped_explicit = [r for r in rows
                        if r["kind_body"] not in ("", "missing_lesson") and r["auto_detected"]]
    if flipped_explicit:
        print(f"\nWARNING: {len(flipped_explicit)} non-missing_lesson kinds auto-flipped:")
        for r in flipped_explicit:
            print(f"  #{r['number']} kind_body={r['kind_body']} -> {r['kind_detected']}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    sys.exit(main())
