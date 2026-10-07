#!/usr/bin/env python3
"""Sync answered GitHub issues into the D1 questions table.

Usage:
    python3 scripts/sync_answered_questions.py --issue 1234
    python3 scripts/sync_answered_questions.py --cron
"""

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime, timezone

import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_OWNER = "Ikalus1988"
REPO_NAME = "MisakaNet"
GITHUB_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
D1_URL = os.environ.get("D1_URL", "")
D1_TOKEN = os.environ.get("D1_TOKEN", "")

# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def gh_get(path: str, params: dict | None = None) -> dict:
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    resp = requests.get(f"{GITHUB_API}{path}", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def gh_patch(path: str, body: dict) -> dict:
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.patch(f"{GITHUB_API}{path}", headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Parse **Kind:** from issue body
# ---------------------------------------------------------------------------

KIND_RE = re.compile(r"^\s*\*\*\s*Kind\s*:\s*(.+?)\s*\*\*$", re.MULTILINE | re.IGNORECASE)
PROBLEM_RE = re.compile(
    r"(?i)^#{2,3}\s*What\h+should\h+(?:I|we)\h+do\?.*",
    re.MULTILINE,
)


def parse_kind_and_problem(body: str) -> tuple[str, str | None, str | None]:
    """Return (kind, problem_text, first_code_block)."""
    kind_m = KIND_RE.search(body)
    kind = kind_m.group(1).strip().lower() if kind_m else ""

    problem_m = PROBLEM_RE.search(body)
    problem_text = problem_m.group(0) if problem_m else None

    code_m = re.search(r"```(?:\w+)?\n(.*?)```", body, re.DOTALL)
    first_code_block = code_m.group(1).strip() if code_m else None

    return kind, problem_text, first_code_block


# ---------------------------------------------------------------------------
# Fetch question issues
# ---------------------------------------------------------------------------

def fetch_question_issues(cursor: str | None = None) -> tuple[list[dict], str | None]:
    """Return (issues_with_question_label, next_cursor).

    Issues that have the `question` label but NO `**Kind:**` line in the body
    are included so the caller can handle the mismatch consistently across
    both the cron and the one-shot `--issue` paths.
    """
    per_page = 100
    params: dict[str, object] = {
        "state": "all",
        "labels": "question",
        "per_page": per_page,
    }
    if cursor:
        params["page"] = cursor

    data = gh_get("/issues", params=params)
    next_cursor: str | None = None
    resp_headers = getattr(data, "headers", None) or {}
    link_header = resp_headers.get("link", "") if resp_headers else ""
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            m = re.search(r"<([^>]+)>", part)
            if m:
                next_cursor = m.group(1).split("?page=")[1].split("&")[0]

    # Split into: has-kind (definite questions) and no-kind (label-only suspects)
    definite: list[dict] = []
    suspicious: list[dict] = []
    for issue in data:
        body = issue.get("body") or ""
        kind, _, _ = parse_kind_and_problem(body)
        if kind == "question":
            definite.append(issue)
        else:
            suspicious.append(issue)

    return definite, suspicious, next_cursor


# ---------------------------------------------------------------------------
# D1 helpers
# ---------------------------------------------------------------------------

def d1_query(sql: str, args: list | None = None) -> list[dict]:
    payload: dict[str, object] = {"sql": sql}
    if args is not None:
        payload["args"] = args
    headers = {"Authorization": f"Bearer {D1_TOKEN}"}
    resp = requests.post(D1_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result.get("result", [])


def d1_exec(sql: str, args: list | None = None) -> None:
    payload: dict[str, object] = {"sql": sql}
    if args is not None:
        payload["args"] = args
    headers = {"Authorization": f"Bearer {D1_TOKEN}"}
    resp = requests.post(D1_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def upsert_question(issue: dict, kind: str) -> None:
    """Upsert a single issue into D1 questions table."""
    body = issue.get("body") or ""
    number = issue["number"]
    state = issue["state"]
    title = issue.get("title", "")
    created_at = issue.get("created_at", "")
    closed_at = issue.get("closed_at") or ""
    author = issue.get("user", {}).get("login", "")
    labels = [lb["name"] for lb in issue.get("labels", [])]

    kind, problem_text, first_code_block = parse_kind_and_problem(body)

    # Normalize kind
    kind = kind or "unknown"

    # Determine answered status
    is_answered = state == "closed" and kind == "question"

    # Check if already exists
    existing = d1_query(
        "SELECT id, answered, kind FROM questions WHERE issue_number = ?",
        [number],
    )

    if existing:
        d1_exec(
            "UPDATE questions SET kind=?, answered=?, problem_text=?, "
            "first_code_block=?, updated_at=CURRENT_TIMESTAMP WHERE issue_number=?",
            [kind, is_answered, problem_text, first_code_block, number],
        )
    else:
        d1_exec(
            "INSERT INTO questions (issue_number, title, kind, answered, "
            "problem_text, first_code_block, created_at, closed_at, author, labels, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [
                number, title, kind, is_answered,
                problem_text, first_code_block,
                created_at, closed_at, author,
                json.dumps(labels),
            ],
        )


def sync_issue(issue_number: int) -> int:
    """Sync a single issue. Returns 0 on success, 1 on error/skip."""
    issue = gh_get(f"/issues/{issue_number}")

    labels = [lb["name"] for lb in issue.get("labels", [])]
    if "question" not in labels:
        print(f"#{issue_number}: no 'question' label, skipping")
        return 0

    kind, _, _ = parse_kind_and_problem(issue.get("body") or "")

    # Allow question label to stand when **Kind:** line is absent.
    # This makes the --issue path consistent with the cron path, which
    # already falls through to treating label-only issues as questions.
    if kind != "question" and kind:
        print(f"#{issue_number}: label says question but kind={kind!r}, proceeding anyway")
    elif not kind:
        print(f"#{issue_number}: no **Kind:** line in body, treating label as source of truth")

    upsert_question(issue, kind or "question")
    return 0


def sync_all() -> None:
    """Full cron sync over all question-labeled issues."""
    cursor: str | None = None
    total = 0
    definite_count = 0
    suspicious_count = 0
    errors: list[str] = []

    while True:
        definite, suspicious, cursor = fetch_question_issues(cursor)
        definite_count += len(definite)
        suspicious_count += len(suspicious)

        for issue in definite + suspicious:
            try:
                n = issue["number"]
                upsert_question(issue, "question")
                total += 1
            except Exception as e:
                errors.append(f"#{issue['number']}: {e}")

        if not cursor:
            break

    print(f"\nSynced {total} question-labeled issues "
          f"({definite_count} with **Kind:**, {suspicious_count} label-only)")
    if errors:
        print(f"Errors ({len(errors)}):")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Sync GitHub questions to D1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", type=int, help="Sync a single issue by number")
    group.add_argument("--cron", action="store_true", help="Run full cron sync")
    args = parser.parse_args()

    if args.issue:
        rc = sync_issue(args.issue)
        sys.exit(rc)
    elif args.cron:
        sync_all()


if __name__ == "__main__":
    main()
