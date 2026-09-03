#!/usr/bin/env python3
"""Sync answered/pending question intakes into the D1 ``questions`` table.

PRD ⑤ §9 (pull-based answer delivery): the worker records ``pending`` rows
for new question intakes; this script closes the loop from GitHub:

- open ``kind=question`` issues  -> ensure a ``pending`` row exists
- closed issues carrying the ``answered`` label -> extract the maintainer's
  answer comment and upsert a ``status='answered'`` row (issue_number unique)

The dedup_hash mirrors the worker's FNV-1a ``hashString(dedupSource)`` where
``dedupSource = f"{kind}:{problem}:{error}"`` — same scheme, so a later
same-question re-submission (worker dedup path) finds the row and returns the
answer.

Usage:
    python3 scripts/sync_answered_questions.py            # full sync
    python3 scripts/sync_answered_questions.py --issue 1362 --execute
    python3 scripts/sync_answered_questions.py --dry-run

Auth:
    GH_TOKEN / GITHUB_TOKEN (read issues+comments)
    CLOUDFLARE_API_TOKEN + account/db from scripts.intake_pipeline
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "Ikalus1988/MisakaNet"
API = f"https://api.github.com/repos/{REPO}"

ANSWER_MARKERS = ("<!-- misakanet-answer -->", "## ✅ Answered", "## [ANSWER]")
AUTOMATED_MARKERS = ("<!-- misakanet-intake-triage -->", "<!-- misakanet-intake-question -->",
                     "<!-- misakanet-question-clarification -->", "<!-- misakanet-question-reclassification -->",
                     "<!-- misakanet-smoke-test -->", "<!-- misakanet-duplicate -->",
                     "## MCP Intake Triage", "## [QUESTION]", "## [REJECTED]")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def fnv1a_hex(s: str) -> str:
    """Mirror workers/register-proxy-sw.js hashString (FNV-1a 32-bit, hex8)."""
    h = 0x811C9DC5
    for ch in str(s):
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


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


def gh_api(path: str, retries: int = 4) -> dict | list:
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(API + path, headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "misakanet-question-sync",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 404 and "/search/" not in path:
                return []
            last = e
        except Exception as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise last


def parse_kind_and_problem(body: str) -> tuple[str, str, str]:
    """Return (kind, problem, error) as the worker would have stored them."""
    kind = ""
    m = re.search(r"\*\*Kind:\*\*\s*([^\n]+)", body, re.I)
    if m:
        kind = m.group(1).strip().lower()
    def section(name: str) -> str:
        m = re.search(rf"##\s+{name}\s*\n(.*?)(?=\n##|\n---|\Z)", body, re.S)
        return m.group(1).strip() if m else ""
    problem = section("Problem")
    error = section("Error")
    if not problem:
        cleaned = re.sub(r"<details>[\s\S]*?</details>", " ", body)
        cleaned = re.sub(r"^\*\*(Kind|Source|Dedup):\*\*.*$", "", cleaned, flags=re.M)
        problem = "\n".join(l for l in cleaned.splitlines() if l.strip())[:2000]
    return kind, problem[:2000], error[:1000]


def fetch_question_issues(closed: bool) -> list[dict]:
    """Issues with the 'question' label whose body Kind == question."""
    results: list[dict] = []
    page = 1
    while page <= 10:
        state = "closed" if closed else "open"
        d = gh_api(f"/issues?state={state}&labels=question&per_page=100&page={page}")
        if not isinstance(d, list) or not d:
            break
        for issue in d:
            if "pull_request" in issue:
                continue
            kind, _, _ = parse_kind_and_problem(issue.get("body") or "")
            if kind == "question":
                results.append(issue)
        if len(d) < 100:
            break
        page += 1
    return results


def fetch_issue_comments(issue_number: int) -> list[dict]:
    out: list[dict] = []
    page = 1
    while page <= 5:
        d = gh_api(f"/issues/{issue_number}/comments?per_page=100&page={page}")
        if not isinstance(d, list) or not d:
            break
        out.extend(d)
        if len(d) < 100:
            break
        page += 1
    return out


def extract_answer(comments: list[dict]) -> tuple[str | None, str | None, int | None]:
    """Find the maintainer answer comment. Returns (answer, created_at, comment_id)."""
    for c in comments:
        body = c.get("body") or ""
        if any(m in body for m in ANSWER_MARKERS) and not any(a in body for a in AUTOMATED_MARKERS):
            return body, c.get("created_at"), c.get("id")
    # Fallback: last non-automated, non-bot comment.
    for c in reversed(comments):
        body = c.get("body") or ""
        user = (c.get("user") or {}).get("login") or ""
        if user.endswith("[bot]"):
            continue
        if any(a in body for a in AUTOMATED_MARKERS):
            continue
        if len(body) > 100:
            return body, c.get("created_at"), c.get("id")
    return None, None, None


def d1_query(sql: str, params: list | None = None) -> dict:
    """Run a query against the misakanet-db D1 (same helper as intake_pipeline)."""
    from scripts.intake_pipeline import _d1_query  # local import
    return _d1_query(sql, params)


def row_exists(issue_number: int) -> bool:
    res = d1_query(
        "SELECT issue_number FROM questions WHERE issue_number = ?1 LIMIT 1", [issue_number])
    try:
        rows = (res.get("result") or [{}])[0].get("results") or []
    except Exception:
        rows = []
    return len(rows) > 0


def upsert_pending(issue: dict) -> bool:
    body = issue.get("body") or ""
    kind, problem, error = parse_kind_and_problem(body)
    dedup = fnv1a_hex(f"{kind}:{problem}:{error}".strip())
    issue_url = issue.get("html_url") or ""
    if not row_exists(issue["number"]):
        d1_query(
            "INSERT INTO questions (issue_number, dedup_hash, problem, source, status, issue_url, created, updated) "
            "VALUES (?1, ?2, ?3, 'github', 'pending', ?4, datetime('now'), datetime('now'))",
            [issue["number"], dedup, problem, issue_url])
        return True
    # refresh dedup hash (schema older rows may lack it)
    d1_query(
        "UPDATE questions SET dedup_hash=?1, updated=datetime('now') WHERE issue_number=?2 AND (dedup_hash IS NULL OR dedup_hash='')",
        [dedup, issue["number"]])
    return False


def upsert_answered(issue: dict) -> bool:
    body = issue.get("body") or ""
    kind, problem, error = parse_kind_and_problem(body)
    dedup = fnv1a_hex(f"{kind}:{problem}:{error}".strip())
    answer, answered_at, comment_id = extract_answer(fetch_issue_comments(issue["number"]))
    if not answer:
        return False
    issue_url = issue.get("html_url") or ""
    closed_at = issue.get("closed_at") or ""
    ts = answered_at or closed_at or datetime.now(timezone.utc).isoformat()
    if row_exists(issue["number"]):
        d1_query(
            "UPDATE questions SET status='answered', answer=?1, answer_comment_id=?2, issue_url=?3, "
            "dedup_hash=?4, answered_at=?5, updated=datetime('now') WHERE issue_number=?6",
            [answer[:20000], comment_id, issue_url, dedup, ts, issue["number"]])
    else:
        d1_query(
            "INSERT INTO questions (issue_number, dedup_hash, problem, source, status, answer, "
            "answer_comment_id, issue_url, answered_at, created, updated) "
            "VALUES (?1, ?2, ?3, 'github', 'answered', ?4, ?5, ?6, ?7, datetime('now'), datetime('now'))",
            [issue["number"], dedup, problem, answer[:20000], comment_id, issue_url, ts])
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--issue", type=int, help="sync a single issue number (any kind=question state)")
    ap.add_argument("--dry-run", action="store_true", help="report what would change without writing")
    args = ap.parse_args()

    if args.dry_run:
        print("dry-run mode: no D1 writes")
        # Verify table exists (schema applied) without writing.
        try:
            d1_query("SELECT COUNT(*) AS n FROM questions")
            print("questions table present")
        except Exception as e:
            print(f"questions table NOT present — apply workers/d1/schema.sql first ({e})")
            return 2

    if args.issue:
        issue = gh_api(f"/issues/{args.issue}")
        kind, _, _ = parse_kind_and_problem(issue.get("body") or "")
        if kind != "question":
            print(f"#{args.issue} is not a question intake (kind={kind!r})")
            return 1
        labels = {l["name"] for l in issue.get("labels", [])}
        if issue["state"] == "open":
            if args.dry_run:
                print(f"#{args.issue}: would ensure pending row")
            else:
                upsert_pending(issue)
                print(f"#{args.issue}: pending row ensured")
        else:
            if "answered" in labels:
                if args.dry_run:
                    print(f"#{args.issue}: would mark answered")
                else:
                    ok = upsert_answered(issue)
                    print(f"#{args.issue}: {'answered row upserted' if ok else 'no answer comment found (skipped)'}")
            else:
                print(f"#{args.issue}: closed without 'answered' label — skipped")
        return 0

    open_issues = fetch_question_issues(closed=False)
    closed_issues = fetch_question_issues(closed=True)
    print(f"open question issues: {len(open_issues)}, closed: {len(closed_issues)}")

    pending_n = 0
    for issue in open_issues:
        if args.dry_run:
            pending_n += 1
        elif upsert_pending(issue):
            pending_n += 1
    answered_n = 0
    for issue in closed_issues:
        labels = {l["name"] for l in issue.get("labels", [])}
        if "answered" not in labels:
            continue
        if args.dry_run:
            answered_n += 1
        elif upsert_answered(issue):
            answered_n += 1
    print(f"{'would upsert' if args.dry_run else 'upserted'} pending={pending_n} answered={answered_n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
