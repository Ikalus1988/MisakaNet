#!/usr/bin/env python3
"""
Intake Pipeline (PRD ③) — parse → classify → draft → precheck → persist → notify.

Chains existing MisakaNet intake logic into one idempotent pipeline whose
output lands in D1 (lesson_drafts table) and surfaces a GitHub issue for
maintainer review. Designed to run either standalone (CI / local) or as the
body of a Cloudflare Workflows step.

Usage:
    python3 scripts/intake_pipeline.py --input '{"kind":"missing_lesson","problem":"...","source":"mcp"}' [--dry-run]
    echo '<json>' | python3 scripts/intake_pipeline.py --stdin
    python3 scripts/intake_pipeline.py --json-file intake.json

Auth for D1 + GitHub:
    - D1: CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID (CI) or mcporter OAuth
    - GitHub issue: GH_TOKEN env (or GITHUB_TOKEN)

Idempotent: lesson_drafts has UNIQUE(source_id, kind); re-runs skip.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CF_ACCOUNT = "6b92325b505f2b76aec49e9fe4195d31"
D1_NAME = "misakanet-db"
D1_ID = os.environ.get("MISAKANET_D1_ID", "b9adbe87-6bbf-4d2f-ae56-41c3487b2831")
MC = str(REPO / ".tools" / "bin" / "mcporter")
CFG = str(REPO / ".tools" / "mcporter.json")

VALID_KINDS = {"missing_lesson", "stale_lesson", "new_lesson_candidate", "question"}


# ── Step 2: parse ──
def parse_intake(raw: dict) -> dict:
    """Normalize an intake payload into pipeline fields."""
    kind = raw.get("kind", "missing_lesson")
    if kind not in VALID_KINDS:
        kind = "missing_lesson"
    return {
        "kind": kind,
        "source": raw.get("source", "mcp"),
        "source_id": raw.get("source_id") or f"mcp-{int(time.time()*1000)}",
        "title": (raw.get("title") or "").strip()[:120],
        "problem": (raw.get("problem") or "").strip(),
        "error": (raw.get("error") or "").strip(),
        "what_tried": (raw.get("what_tried") or "").strip(),
        "fix": (raw.get("fix") or "").strip(),
        "verification": (raw.get("verification") or "").strip(),
        "domain": (raw.get("domain") or "").strip(),
        "tags": raw.get("tags") or [],
    }


# ── Step 3: classify ──
def classify(intake: dict) -> dict:
    """Infer domain + coarse type; returns {domain, type}."""
    text = " ".join(filter(None, [intake["title"], intake["problem"], intake["error"]])).lower()
    domain_hints = {
        "python": ["python", "pip", "venv", "django", "flask", "traceback", "asyncio"],
        "devops": ["docker", "k8s", "kubernetes", "ci", "github actions", "deploy", "terraform"],
        "network": ["network", "proxy", "timeout", "dns", "tls", "ssl", "connect"],
        "feishu": ["feishu", "lark", "飞书"],
        "rag": ["rag", "embedding", "vector", "retrieval", "bm25", "chroma"],
        "mcp": ["mcp", "model context protocol", "tool call"],
        "fanuc": ["fanuc", "karel", "robot", "plc"],
    }
    domain = intake["domain"] or "general"
    if not intake["domain"]:
        for d, hints in domain_hints.items():
            if any(h in text for h in hints):
                domain = d
                break
    type_ = "lesson"
    if intake["kind"] == "question":
        type_ = "question"
    elif intake["kind"] == "stale_lesson":
        type_ = "stale"
    return {"domain": domain, "type": type_}


# ── Step 4: draft ──
def generate_draft(intake: dict, cls: dict) -> dict:
    """Build a lesson-draft markdown (frontmatter + skeleton sections)."""
    title = intake["title"] or (intake["problem"][:80] if intake["problem"] else "Untitled failure")
    slug_base = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    slug = re.sub(r"[\s_]+", "-", slug_base)[:60].strip("-") or "untitled"
    tags = intake["tags"] or []
    if intake["domain"] and intake["domain"] not in tags:
        tags = [intake["domain"]] + tags
    fm = {
        "title": title,
        "domain": cls["domain"],
        "status": "draft",
        "source": intake["source"],
        "tags": tags[:8],
        "created": time.strftime("%Y-%m-%d"),
    }
    sections = [f"## Problem\n\n{intake['problem']}"]
    if intake["error"]:
        sections.append(f"## Error\n\n```\n{intake['error'][:2000]}\n```")
    if intake["what_tried"]:
        sections.append(f"## What was tried\n\n{intake['what_tried']}")
    if intake["fix"]:
        sections.append(f"## Solution\n\n{intake['fix']}")
    else:
        sections.append("## Solution\n\n_(pending review — no fix recorded)_")
    if intake["verification"]:
        sections.append(f"## Verification\n\n{intake['verification']}")
    else:
        sections.append("## Verification\n\n_(pending review)_")
    md = "---\n" + json.dumps(fm, ensure_ascii=False, indent=2) + "\n---\n\n" + "\n\n".join(sections) + "\n"
    return {"slug": slug, "content_md": md, "title": title, "tags": tags}


# ── Step 5: precheck ──
def precheck(intake: dict, draft: dict) -> dict:
    """Lightweight quality gate: length / verification / redaction presence."""
    issues = []
    if len(intake["problem"]) < 20:
        issues.append("PROBLEM_TOO_SHORT: problem should be ≥20 chars")
    if not intake["verification"] and not intake["fix"]:
        issues.append("NO_FIX_OR_VERIFICATION: provide at least a fix or verification")
    if re.search(r"(ghp_|github_pat_|AKIA[0-9A-Z]{16}|sk-[a-zA-Z0-9]{20,})", intake["problem"]):
        issues.append("SECRET_PATTERN: possible credential in problem (must be redacted)")
    body_len = len(draft["content_md"])
    if body_len < 100:
        issues.append(f"BODY_TOO_SHORT: draft body is {body_len} chars (<100)")
    score = max(0, 100 - len(issues) * 15)
    return {"score": score, "issues": issues, "body_len": body_len,
            "pass": len(issues) <= 1, "verified": bool(intake["verification"])}


# ── Step 6: persist to D1 ──
def _d1_query(sql: str, params: list | None = None) -> dict:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    body = {"sql": sql}
    if params:
        body["params"] = params
    if token:
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/d1/database/{D1_ID}/query",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                     "User-Agent": "misakanet-intake"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    # mcporter OAuth path
    code = (f"async () => {{ const r = await cloudflare.request({{ method: 'POST', "
            f"path: '/accounts/{CF_ACCOUNT}/d1/database/{D1_ID}/query', "
            f"body: {json.dumps(body)} }}); return r.result; }}")
    r = subprocess.run([MC, "call", "cloudflare.execute", "code=" + code, "--config", CFG],
                       capture_output=True, text=True, timeout=90)
    return json.loads(r.stdout.strip()) if r.stdout.strip() else {}


def persist_draft(intake: dict, cls: dict, draft: dict, pre: dict) -> bool:
    """Upsert into lesson_drafts; returns True if newly inserted (not a dup)."""
    sql = (
        "INSERT INTO lesson_drafts "
        "(id, kind, source, source_id, status, title, domain, tags, problem, "
        " root_cause, solution, verification, content_md, precheck, created, updated) "
        "VALUES (?1,?2,?3,?4,'prechecked',?5,?6,?7,?8,'',?9,?10,?11,?12,datetime('now'),datetime('now')) "
        "ON CONFLICT(source_id, kind) DO NOTHING"
    )
    params = [
        draft["slug"], intake["kind"], intake["source"], intake["source_id"],
        draft["title"], cls["domain"], json.dumps(draft["tags"], ensure_ascii=False),
        intake["problem"][:2000], intake["fix"][:4000], intake["verification"][:2000],
        draft["content_md"], json.dumps(pre, ensure_ascii=False),
    ]
    try:
        res = _d1_query(sql, params)
        # D1 REST returns results[0].meta.changes
        meta = ((res.get("result") or [{}])[0].get("meta") or {})
        return int(meta.get("changes", 0) or 0) > 0
    except Exception as e:
        print(f"  ⚠️ persist failed: {e}", file=sys.stderr)
        return False


# ── Step 7: notify (GitHub issue) ──
def _question_issue_payload(intake: dict) -> tuple[str, list[str], str]:
    """Build ([Question] issue) title/labels/body.

    Questions are NOT lesson candidates (see #1396): the body carries the
    Kind marker the intake workflows route on, and the copy asks the submitter
    to add failure shape if a lesson is what they actually need.
    """
    problem = (intake["problem"] or "").strip()[:2000]
    first_line = (problem.splitlines() or ["help request"])[0][:80]
    title = f"[Question] {first_line}"
    labels = ["intake", "mcp-intake", "pending-review", "needs-human-review", "question"]
    body = (
        f"**Kind:** question\n**Source:** {intake['source']}\n"
        f"**Dedup:** `{intake['source_id'] or 'n/a'}`\n\n"
        f"## Problem\n\n{problem or '_no problem text_'}\n\n"
        f"---\n_Generated by intake-pipeline (PRD ③). Question / knowledge-gap — "
        f"NOT a lesson candidate, so no lesson draft was created. To turn this into "
        f"a lesson, reply with ## Error, ## What was tried, and ## Verification._"
    )
    return title, labels, body


def notify_question(intake: dict) -> dict | None:
    """Open a [Question] issue without minting a lesson draft (see #1396)."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("  ⚠️ GH_TOKEN not set — skipping issue creation", file=sys.stderr)
        return None
    title, labels, body = _question_issue_payload(intake)
    req = urllib.request.Request(
        "https://api.github.com/repos/Ikalus1988/MisakaNet/issues",
        data=json.dumps({"title": title, "body": body, "labels": labels}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "Accept": "application/vnd.github.v3+json", "User-Agent": "misakanet-intake"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        return {"issue_number": d.get("number"), "issue_url": d.get("html_url")}
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ question issue creation failed: {e.code} {e.read()[:200]}", file=sys.stderr)
        return None


def notify(intake: dict, cls: dict, draft: dict, pre: dict, is_new: bool) -> dict | None:
    if not is_new:
        return None  # duplicate intake — don't spam issues
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("  ⚠️ GH_TOKEN not set — skipping issue creation", file=sys.stderr)
        return None
    prefix = "[Question]" if intake["kind"] == "question" else "[Intake]"
    labels = ["intake", "mcp-intake", "pending-review"]
    if intake["kind"] == "question":
        labels.append("needs-human-review")
    body = (
        f"**Kind:** {intake['kind']}\n**Source:** {intake['source']}\n"
        f"**Domain:** {cls['domain']}\n**Precheck:** score {pre['score']} — "
        f"{'pass' if pre['pass'] else 'needs work'}\n"
        f"**Issues:** {', '.join(pre['issues']) or 'none'}\n\n"
        f"## Draft\n\n```markdown\n{draft['content_md'][:3000]}\n```\n\n"
        f"---\n_Generated by intake-pipeline (PRD ③). Review and promote to lessons/._"
    )
    req = urllib.request.Request(
        "https://api.github.com/repos/Ikalus1988/MisakaNet/issues",
        data=json.dumps({"title": f"{prefix} {draft['title'][:80]}", "body": body, "labels": labels}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "Accept": "application/vnd.github.v3+json", "User-Agent": "misakanet-intake"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        return {"issue_number": d.get("number"), "issue_url": d.get("html_url")}
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ issue creation failed: {e.code} {e.read()[:200]}", file=sys.stderr)
        return None


def run(intake_raw: dict, dry_run: bool = False) -> dict:
    intake = parse_intake(intake_raw)

    # Question / knowledge-gap intakes are NOT lesson candidates (see #1396):
    # never mint a lesson-shaped draft into lesson_drafts. Route straight to a
    # [Question] issue so the intake workflows treat it as a question.
    if intake["kind"] == "question":
        result = {
            "kind": intake["kind"], "source": intake["source"],
            "source_id": intake["source_id"],
            "routed_as": "question",
            "note": "Questions are not lesson candidates — no lesson draft was created.",
        }
        if dry_run:
            result["dry_run"] = True
            result["draft_preview"] = f"[Question] {(intake['problem'].splitlines() or ['help request'])[0][:80]}"
            return result
        issue = notify_question(intake)
        if issue:
            result["issue"] = issue
        return result

    cls = classify(intake)
    draft = generate_draft(intake, cls)
    pre = precheck(intake, draft)
    result = {
        "kind": intake["kind"], "source": intake["source"], "source_id": intake["source_id"],
        "slug": draft["slug"], "domain": cls["domain"], "precheck": pre,
    }
    if dry_run:
        result["dry_run"] = True
        result["draft_preview"] = draft["content_md"][:200]
        return result
    is_new = persist_draft(intake, cls, draft, pre)
    issue = notify(intake, cls, draft, pre, is_new)
    result["persisted"] = is_new
    result["duplicate"] = not is_new
    if issue:
        result["issue"] = issue
        # Backfill the linked issue into the draft row (PRD ③ step 7).
        try:
            _d1_query(
                "UPDATE lesson_drafts SET issue_number=?1, issue_url=?2, "
                "status='review', updated=datetime('now') WHERE source_id=?3 AND kind=?4",
                [issue["issue_number"], issue["issue_url"], intake["source_id"], intake["kind"]],
            )
        except Exception as e:
            print(f"  ⚠️ issue backfill failed: {e}", file=sys.stderr)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Intake pipeline (PRD ③)")
    ap.add_argument("--input", help="JSON intake payload as string")
    ap.add_argument("--stdin", action="store_true", help="read JSON from stdin")
    ap.add_argument("--json-file", help="read JSON from file")
    ap.add_argument("--dry-run", action="store_true", help="parse/classify/draft/precheck only")
    args = ap.parse_args()

    raw = None
    if args.input:
        raw = json.loads(args.input)
    elif args.json_file:
        raw = json.loads(Path(args.json_file).read_text())
    elif args.stdin:
        raw = json.loads(sys.stdin.read())
    else:
        print(__doc__)
        return 2
    result = run(raw, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
