#!/usr/bin/env python3
"""Propose the three optional structured fields for lessons that lack them.

Why this exists
---------------
Measured 2026-10-28: **394 of 651 lessons (61%)** have no `summary_plain`, no `trigger`, no `verify`.
Those are the fields the reading contract depends on — `AGENTS.md` tells an agent to say
`summary_plain` to the user verbatim on a hit, and without it the agent has to invent a sentence from
the Problem section, which is exactly the paraphrase the field was added to prevent. `trigger` is what
makes a lesson findable at the moment it applies; `verify` is what makes a fix checkable instead of
hopeful.

The work is generative and mechanical, which is the shape a free plan fits: this uses **Workers AI**,
already included in the Workers Paid plan, so it consumes no external quota and no separate budget.
(`GEMINI_API_KEY` is used only if `--provider gemini` is asked for, which is the free-tier path.)

What it does not do
-------------------
It does not edit 394 files in one commit. `--propose` (the default) writes a JSON review file; `--apply`
writes the fields into the frontmatter of the lessons it proposed, one YAML key each, and the caller is
expected to pass `--limit` while the prompt is being tuned. A generation pass that silently rewrites
most of the corpus is not a backfill, it is a rewrite.

Usage
-----
    python3 scripts/backfill_structured_fields.py --limit 5 --propose out.json
    python3 scripts/backfill_structured_fields.py --limit 5 --apply
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_JSON = REPO / "data" / "lessons.json"
LESSONS_DIR = REPO / "lessons"
FIELDS = ("summary_plain", "trigger", "verify")

WORKERS_AI_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "gemini-3.1-flash-lite:generateContent?key={key}")

PROMPT = """You are writing three metadata fields for a debugging lesson. Answer with ONE JSON object \
and nothing else.

Lesson title: {title}
Domain: {domain}

Problem:
{problem}

Fix:
{fix}

Write, in the SAME language as the lesson:
- "summary_plain": one sentence a developer would say out loud to a colleague, naming what broke and \
what fixed it. No markdown, no code, at most 180 characters.
- "trigger": when this lesson applies, as a short condition ("when X fails with Y"). At most 140 characters.
- "verify": one command or observation that proves the fix worked. At most 140 characters.

Reply with exactly: {{"summary_plain": "...", "trigger": "...", "verify": "..."}}"""


def missing_rows(limit: int | None) -> list[dict]:
    rows = json.loads(LESSONS_JSON.read_text(encoding="utf-8"))
    out = [row for row in rows if not str(row.get("summary_plain") or "").strip()]
    return out[:limit] if limit else out


def lesson_text(row: dict) -> str:
    path = LESSONS_DIR / str(row.get("url") or "").removeprefix("lessons/")
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def problem_and_fix(body: str, row: dict) -> tuple[str, str]:
    """The Problem and Fix sections, falling back to the index's `summary`."""
    def section(name: str) -> str:
        match = re.search(rf"^#+\s*{name}\s*$(.*?)(?=^#+\s|\Z)", body, re.M | re.S | re.I)
        return (match.group(1).strip() if match else "")

    problem = section("Problem") or str(row.get("summary") or "")
    fix = section("Fix") or section("Solution") or section("Root Cause")
    return problem[:2500], fix[:1500]


def call_workers_ai(prompt: str, account: str, token: str, model: str) -> str:
    payload = json.dumps({"messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 400}).encode()
    request = urllib.request.Request(
        WORKERS_AI_URL.format(account=account, model=model), data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    # Cloudflare's API must bypass a local proxy: it answers 000/403 through one.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    result = data.get("result") or {}
    text = result.get("response", result)
    # Workers AI returns `response` as a string for some models and as an object for others; the
    # parser downstream expects text either way.
    return text if isinstance(text, str) else json.dumps(text)


def call_gemini(prompt: str, key: str) -> str:
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
    request = urllib.request.Request(
        GEMINI_URL.format(key=key), data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"]


def parse_fields(raw: str) -> dict | None:
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    cleaned = {}
    for field in FIELDS:
        value = str(data.get(field) or "").strip().replace("\n", " ")
        if not value:
            return None
        cleaned[field] = value[:200]
    return cleaned


def in_frontmatter(row: dict, fields: dict) -> bool:
    """Insert the keys before the closing `---`. Idempotent: an existing key is left alone."""
    path = LESSONS_DIR / str(row.get("url") or "").removeprefix("lessons/")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end < 0:
        return False
    head, tail = text[:end], text[end:]
    added = [f"{key}: {json.dumps(value, ensure_ascii=False)}"
             for key, value in fields.items()
             if not re.search(rf"^{key}\s*:", head, re.M)]
    if not added:
        return False
    path.write_text(head + "\n" + "\n".join(added) + tail, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=None, help="how many lessons to process")
    ap.add_argument("--propose", type=Path, default=None, help="write proposals to this JSON file")
    ap.add_argument("--apply", action="store_true", help="write the fields into the lesson frontmatter")
    ap.add_argument("--provider", choices=("workers-ai", "gemini"), default="workers-ai")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args(argv)

    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "6b92325b505f2b76aec49e9fe4195d31")
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    key = os.environ.get("GEMINI_API_KEY", "")
    if args.provider == "workers-ai" and not token:
        print("CLOUDFLARE_API_TOKEN is not set", file=sys.stderr)
        return 2
    if args.provider == "gemini" and not key:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 2

    rows = missing_rows(args.limit)
    proposals, failures = [], []
    for row in rows:
        body = lesson_text(row)
        problem, fix = problem_and_fix(body, row)
        prompt = PROMPT.format(title=row.get("title"), domain=row.get("domain"),
                               problem=problem, fix=fix)
        try:
            raw = (call_workers_ai(prompt, account, token, args.model)
                   if args.provider == "workers-ai" else call_gemini(prompt, key))
        except (urllib.error.URLError, TimeoutError, KeyError) as error:
            failures.append({"id": row.get("id"), "error": str(error)[:160]})
            continue
        fields = parse_fields(raw)
        if not fields:
            failures.append({"id": row.get("id"), "error": "unparseable", "raw": raw[:200]})
            continue
        proposals.append({"id": row.get("id"), "url": row.get("url"), "title": row.get("title"),
                          "fields": fields})

    if args.propose:
        args.propose.write_text(json.dumps({"proposals": proposals, "failures": failures},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
    written = 0
    if args.apply:
        by_id = {row.get("id"): row for row in rows}
        for proposal in proposals:
            if in_frontmatter(by_id[proposal["id"]], proposal["fields"]):
                written += 1

    print(f"proposed {len(proposals)}, failed {len(failures)}, written {written}")
    for proposal in proposals[:3]:
        print(f"  {proposal['id']}: {proposal['fields']['summary_plain'][:90]}")
    for failure in failures[:3]:
        print(f"  FAILED {failure['id']}: {failure['error'][:80]}")
    return 0 if proposals else 1


if __name__ == "__main__":
    sys.exit(main())
