#!/usr/bin/env python3
"""Sync answered questions from GitHub issues into the D1 database."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import httpx

# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def fnv1a_hex(data: str) -> str:
    """Compute FNV-1a 32-bit hash and return as 8-char lowercase hex string."""
    h = 0x811c9dc5
    for byte in data.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def hash_string(data: str) -> str:
    """Alias for fnv1a_hex – kept for compatibility with JS callers."""
    return fnv1a_hex(data)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_kind_and_problem(body: str) -> tuple[str, str, str]:
    """Extract kind, problem, and error from an issue body.

    The worker stores the *full* (trimmed) problem and error text in the
    dedup source, so we must return the full text here as well – never
    truncate.  Truncating only here makes the stored hash diverge from the
    worker's hash for anything longer than the old hard cap.
    """
    lines = body.splitlines()
    kind = "question"
    problem_lines: list[str] = []
    error_lines: list[str] = []
    in_problem = False
    in_error = False

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("kind:"):
            kind = stripped[5:].strip() or "question"
            in_problem = True
            in_error = False
            continue
        elif stripped.lower().startswith("problem:"):
            problem_lines.append(stripped[8:].strip())
            in_problem = True
            in_error = False
            continue
        elif stripped.lower().startswith("error:"):
            error_lines.append(stripped[6:].strip())
            in_problem = False
            in_error = True
            continue
        elif stripped and not stripped.startswith("#"):
            if in_problem:
                problem_lines.append(stripped)
            elif in_error:
                error_lines.append(stripped)

    problem = " ".join(problem_lines).strip()
    error = " ".join(error_lines).strip()

    # Return full text – no length caps.
    return kind, problem, error


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_OWNER = "Ikalus1988"
REPO_NAME = "MisakaNet"


def github_get(path: str, params: dict | None = None) -> dict:
    url = f"https://api.github.com{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    with httpx.Client() as client:
        resp = client.get(url, headers=headers, params=params, timeout=30.0)
        resp.raise_for_status()
        return resp.json()


def get_issue_labels(issue_number: int) -> list[str]:
    data = github_get(f"/repos/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}")
    return [lbl["name"] for lbl in data.get("labels", [])]


def has_label(issue_number: int, label: str) -> bool:
    return label in get_issue_labels(issue_number)


# ---------------------------------------------------------------------------
# D1 helpers
# ---------------------------------------------------------------------------

D1_URL = os.environ.get("D1_URL", "")
D1_TOKEN = os.environ.get("D1_TOKEN", "")


def d1_query(sql: str, params: list | None = None) -> list[dict]:
    body = {"sql": sql}
    if params:
        body["params"] = params
    payload = json.dumps(body).encode()
    with httpx.Client() as client:
        resp = client.post(
            f"{D1_URL}/query",
            content=payload,
            headers={
                "Authorization": f"Bearer {D1_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("result", [])
        if results and isinstance(results[0], dict):
            keys = results[0].keys()
            return [{k: row[i] for i, k in enumerate(keys)} for row in results]
        return []


def d1_run(sql: str, params: list | None = None) -> None:
    body = {"sql": sql}
    if params:
        body["params"] = params
    payload = json.dumps(body).encode()
    with httpx.Client() as client:
        resp = client.post(
            f"{D1_URL}/query",
            content=payload,
            headers={
                "Authorization": f"Bearer {D1_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def sync_answered_questions(before_issue: int | None = None, limit: int = 100) -> None:
    """Sync answered GitHub issues into D1.

    Only processes issues labelled `answered`.
    """
    page = 1
    synced = 0
    skipped = 0

    while True:
        issues = github_get(
            f"/repos/{REPO_OWNER}/{REPO_NAME}/issues",
            params={
                "state": "all",
                "labels": "answered",
                "page": str(page),
                "per_page": str(limit),
                "sort": "updated",
                "direction": "desc",
            },
        )
        if not issues:
            break

        for issue in issues:
            issue_number = issue["number"]

            if before_issue is not None and issue_number >= before_issue:
                skipped += 1
                continue

            body = issue["body"] or ""
            if not body or "kind:" not in body.lower():
                continue

            kind, problem, error = parse_kind_and_problem(body)
            dedup_source = f"{kind}:{problem}:{error}"
            dedup_hash = fnv1a_hex(dedup_source)

            created_at = datetime.fromisoformat(
                issue["created_at"].replace("Z", "+00:00")
            )
            updated_at = datetime.fromisoformat(
                issue["updated_at"].replace("Z", "+00:00")
            )

            # Upsert into D1
            d1_run(
                """
                INSERT INTO misakanet_intake (
                    issue_number, kind, problem, error,
                    dedup_hash, created_at, updated_at,
                    submitted_at, answered_at, answer,
                    converted, source, duplicate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dedup_hash) DO UPDATE SET
                    issue_number     = excluded.issue_number,
                    kind             = excluded.kind,
                    problem          = excluded.problem,
                    error            = excluded.error,
                    created_at       = excluded.created_at,
                    updated_at       = excluded.updated_at,
                    submitted_at     = excluded.submitted_at,
                    answered_at      = excluded.answered_at,
                    answer           = excluded.answer,
                    converted        = excluded.converted,
                    source           = excluded.source,
                    duplicate        = excluded.duplicate
                """,
                [
                    issue_number,
                    kind,
                    problem,
                    error,
                    dedup_hash,
                    int(created_at.timestamp() * 1000),
                    int(updated_at.timestamp() * 1000),
                    int(created_at.timestamp() * 1000),
                    int(updated_at.timestamp() * 1000),
                    "",  # answer – filled later by triage
                    1,  # converted
                    "github-sync",
                    0,  # duplicate
                ],
            )
            synced += 1
            print(f"  answered row upserted: #{issue_number}  dedup={dedup_hash}")

        # Stop if we've gone past the oldest requested issue
        if issues[-1]["number"] <= (before_issue or 0):
            break
        page += 1

    print(f"\nSync complete: {synced} rows upserted, {skipped} skipped (before #{before_issue or 'none'})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync answered GitHub issues to D1")
    parser.add_argument("--before", type=int, help="Only sync issues with number < this")
    parser.add_argument("--limit", type=int, default=100, help="Page size for GitHub API")
    args = parser.parse_args()

    sync_answered_questions(before_issue=args.before, limit=args.limit)
