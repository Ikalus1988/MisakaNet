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

Questions are not lessons
-------------------------
A `question` intake is routed to a `[Question]` issue (`notify_question`) and never mints a
lesson draft (#1396). Two signals say "this is a question":

* `kind: "question"` — the MCP contract, and the only signal the MCP payload carries;
* an issue label `question` / `type:question` — added to every question intake by
  `.github/workflows/intake-auto-review.yml`. This is the **authoritative** signal when the
  caller has it (the issue is the intake of record), and the payload may carry it under
  `labels` (list or comma string) or `label`.

Labels are **not** part of the MCP `submit_intake` payload (measured against
`docs/mcp-intake-guide.md` and `scripts/mcp_http_server.py`, 2026-10-17), so for the MCP path
the only check the data supports is `kind` — which `workers/lib/utils.js` sets from the
question detector. A lesson `kind` carrying a `question`/`type:question` label is still routed
as a question, because the label is what the issue workflows acted on.
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

#: Labels that mean "this intake is a question", never a lesson candidate.
#: `intake-auto-review.yml` applies both to every intake it routes as a question (#1396).
QUESTION_LABELS = frozenset({"question", "type:question"})

#: What the pipeline says instead of silently dropping a question, and where the question goes.
QUESTION_ROUTE_NOTE = (
    "Questions are not lesson candidates: this intake is routed to a [Question] issue "
    "(scripts/intake_pipeline.py:notify_question) instead of minting a lesson draft. It is "
    "answered there, and once the `answered` label is set the answer reaches the FAQ through "
    ".github/workflows/sync-question-answers.yml — the question channel, not `lessons/`."
)


def _normalized_labels(raw: dict) -> list[str]:
    """Issue labels, when the caller has them, lower-cased and stripped.

    Neither spelling is required: `labels` (list or comma-separated string) and the singular
    `label` are both accepted because the intake paths that have labels pass them differently.
    Anything that is not a string is dropped rather than stringified — a stray number must not
    become a label that happens to match nothing.
    """
    value = raw.get("labels", raw.get("label"))
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return [v.strip().lower() for v in value if isinstance(v, str) and v.strip()]


def question_routed_by(intake: dict) -> str | None:
    """Why this intake is a question, or None. `kind` first, then the issue labels.

    Returns `"kind"` / `"label"` so the caller can report *which* signal fired — "skipped" with
    no reason is the shape that turns a routing rule into a silent drop.
    """
    if intake["kind"] == "question":
        return "kind"
    if QUESTION_LABELS.intersection(intake["labels"]):
        return "label"
    return None


# ── Field caps, and the cut that travels with the draft ─────────────────────
#
# Every cap below used to bite silently, and the silence was the whole defect: a draft that lost
# its tail is still a well-formed draft, so nothing downstream re-checks it. The cost is on
# record. A contributor's final `ASKING` section was sheared off by the 2,000-character cap in
# `generate_draft` and they had to open a follow-up to report the loss — intake #2760, titled
# "the body got cut by 2,000-char truncation (final 'ASKING' section … missing)".
#
# The model is already in this repository: `misakanet_get_lesson` used to truncate the lesson body
# silently and now returns `{truncated, content_length, content_returned, full_content_url}` with
# the response (`workers/register-proxy-sw.js`: "The cut now travels with the response"), after
# 53 of 457 lesson bodies arrived cut in half (2026-09-24). Same rule here, on both surfaces the
# pipeline produces: the draft it writes, and the result it returns.
ERROR_SECTION_CAP = 2000
# intake field -> cap, for the D1 `lesson_drafts` columns. One mapping, read by both the cut and
# the truncation report, so the two cannot disagree about which number applied — the worker's cap
# family cost four rounds to exactly that mismatch ("the fix was a number, not a shape").
DRAFT_COLUMN_CAPS = {"problem": 2000, "fix": 4000, "verification": 2000}
# The draft preview embedded in the notification issue. GitHub caps an issue body at 65,536
# characters; this is a preview of a draft whose full text lives in `lesson_drafts.content_md`,
# not a body limit, so it is deliberately much smaller than `QUESTION_BODY_CAP`.
DRAFT_PREVIEW_CAP = 3000


def _clip(text: str, cap: int, what: str, full_copy: str) -> tuple[str, str]:
    """Return `(head, notice)`. `notice` is `""` when nothing was cut.

    `what` names the surface the text was submitted to and `full_copy` says where the whole text
    still is — or, when this pipeline did not keep it, says that plainly. A notice that only said
    "truncated" would leave the reader with the same question the silent cut did.
    """
    if len(text) <= cap:
        return text, ""
    notice = (
        f"⚠️ **Truncated at {cap:,} characters by intake-pipeline** "
        f"({len(text):,} were submitted to {what}). The text above is the head only. {full_copy}"
    )
    return text[:cap], notice


def _clip_value(text: str, cap: int, what: str, full_copy: str) -> str:
    """`_clip` folded into one storable value — for a D1 column, which has nowhere else to say it."""
    head, notice = _clip(text, cap, what, full_copy)
    return f"{head}\n\n---\n{notice}\n" if notice else head


def truncation_report(intake: dict) -> dict:
    """Which submitted fields had to be cut, and by how much.

    The response half of the same announcement, shaped after `misakanet_get_lesson`'s
    `{truncated, content_length, content_returned, …}`: a caller that never opens the issue can
    still tell from the result alone that part of what it sent was not used.
    """
    out = {}
    for field, cap in [("error", ERROR_SECTION_CAP), *DRAFT_COLUMN_CAPS.items()]:
        submitted = len(intake.get(field) or "")
        if submitted > cap:
            out[field] = {"cap": cap, "content_length": submitted, "content_returned": cap}
    return out


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
        "labels": _normalized_labels(raw),
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
        head, notice = _clip(
            intake["error"], ERROR_SECTION_CAP, "the draft's Error section",
            f"This pipeline keeps only that head, because the draft is the only artifact it "
            f"writes: the full error text is in the intake of record (`{intake['source_id']}`), "
            f"so re-submit the tail there if it carries the evidence.")
        sections.append(f"## Error\n\n```\n{head}\n```" + (f"\n\n---\n{notice}" if notice else ""))
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
    # Each column announces its own cut and points at the copy that still holds the whole text:
    # `content_md` of this same row. The columns are summaries; the draft is the record. The D1
    # column names differ from the payload keys (`fix` is stored in `solution`), so the marker
    # names the column a reader will actually query.
    columns = [
        _clip_value(intake[field], DRAFT_COLUMN_CAPS[field], f"the lesson_drafts.{column} column",
                    "The full text is in `content_md` of this same row.")
        for field, column in (("problem", "problem"), ("fix", "solution"),
                              ("verification", "verification"))
    ]
    params = [
        draft["slug"], intake["kind"], intake["source"], intake["source_id"],
        draft["title"], cls["domain"], json.dumps(draft["tags"], ensure_ascii=False),
        *columns,
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
# GitHub caps an issue body at 65,536 chars; leave headroom for the wrapper.
QUESTION_BODY_CAP = 60_000


def _clip_question(text: str) -> str:
    """Shorten an over-long question body *visibly*.

    A question is the one intake kind whose submitted text IS the deliverable —
    the lesson path summarizes, the question path has to preserve. Clipping it
    silently produces a well-formed issue that quietly lost its evidence, and a
    well-formed issue is the one thing nobody suspects (#2743: a ranked ledger
    arrived as items 1,3,5,7,9,11,13, cut mid-word, because the code-weight
    column was sheared off at 2,000 chars upstream).

    So when the cap does bite, say so and say what to do about it. Under the cap
    the text passes through untouched.
    """
    if len(text) <= QUESTION_BODY_CAP:
        return text
    return (
        text[:QUESTION_BODY_CAP]
        + f"\n\n---\n⚠️ **Truncated at {QUESTION_BODY_CAP:,} characters by "
        f"intake-pipeline** ({len(text):,} were submitted). The text above is the "
        f"head only. If the omitted part carries the evidence, comment with it or "
        f"attach it to this issue.\n"
    )


def _question_issue_payload(intake: dict) -> tuple[str, list[str], str]:
    """Build ([Question] issue) title/labels/body.

    Questions are NOT lesson candidates (see #1396): the body carries the
    Kind marker the intake workflows route on, and the copy asks the submitter
    to add failure shape if a lesson is what they actually need.
    """
    problem = _clip_question((intake["problem"] or "").strip())
    first_line = (problem.splitlines() or ["help request"])[0][:80]
    title = f"[Question] {first_line}"
    labels = ["intake", "mcp-intake", "pending-review", "needs-answer", "question"]
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
        labels.append("needs-answer")
    preview, preview_cut = _clip(
        draft["content_md"], DRAFT_PREVIEW_CAP, "the draft preview in this issue",
        f"The full draft is `lesson_drafts.content_md` for `source_id={intake['source_id']}`; the "
        f"issue carries the head of it so a reviewer can triage without the D1 binding.")
    body = (
        f"**Kind:** {intake['kind']}\n**Source:** {intake['source']}\n"
        f"**Domain:** {cls['domain']}\n**Precheck:** score {pre['score']} — "
        f"{'pass' if pre['pass'] else 'needs work'}\n"
        f"**Issues:** {', '.join(pre['issues']) or 'none'}\n\n"
        f"## Draft\n\n```markdown\n{preview}\n```\n"
        + (f"\n---\n{preview_cut}\n" if preview_cut else "")
        + "\n---\n_Generated by intake-pipeline (PRD ③). Review and promote to lessons/._"
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

    # Question / knowledge-gap intakes are NOT lesson candidates (see #1396): never mint a
    # lesson-shaped draft into lesson_drafts. Route straight to a [Question] issue so the intake
    # workflows treat it as a question. Two signals count (see the module docstring): the MCP
    # `kind` contract, and the `question` / `type:question` issue labels when the caller has
    # them. The skip is announced on stderr as well as in the result: a routing rule whose only
    # trace is a missing draft is indistinguishable from a bug.
    routed_by = question_routed_by(intake)
    if routed_by:
        reason = ("kind=question" if routed_by == "kind"
                  else "issue label question/type:question")
        print(f"  ↪ question intake ({reason}) — no lesson draft minted; "
              f"routed to a [Question] issue, answered there.", file=sys.stderr)
        result = {
            "kind": intake["kind"], "source": intake["source"],
            "source_id": intake["source_id"],
            "routed_as": "question",
            "routed_by": routed_by,
            "note": QUESTION_ROUTE_NOTE,
        }
        # The question body is the deliverable, and `_clip_question` announces its 60,000-char cut
        # in the issue. The response says it too, so a caller that only reads the result is not
        # left thinking the whole question arrived (#2760 was reported by a human who noticed a
        # missing section, because nothing in the response told them).
        if len(intake["problem"]) > QUESTION_BODY_CAP:
            result["truncated"] = True
            result["truncations"] = {"problem": {
                "cap": QUESTION_BODY_CAP,
                "content_length": len(intake["problem"]),
                "content_returned": QUESTION_BODY_CAP,
            }}
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
    cuts = truncation_report(intake)
    result = {
        "kind": intake["kind"], "source": intake["source"], "source_id": intake["source_id"],
        "slug": draft["slug"], "domain": cls["domain"], "precheck": pre,
    }
    if cuts:
        # The same announcement, on the surface the caller reads. Without it the caller sees
        # `persisted: true` and a slug — a successful-looking response for a submission whose tail
        # was dropped, which is the #2760 shape one level up.
        result["truncated"] = True
        result["truncations"] = cuts
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
