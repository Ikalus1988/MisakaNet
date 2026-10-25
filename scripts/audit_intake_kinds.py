#!/usr/bin/env python3
"""Audit historical intake issues: question vs lesson discrimination (#1396).

For every GitHub intake issue (labels ``intake``/``mcp-intake``), compare the
kind recorded in the issue body (``**Kind:**``) with what the current
question detector (:func:`scripts.intake_kind.infer_intake_kind`) would decide
from the submitted problem text alone.

Two checks run on **every** invocation, before any mode can return:

1. *flagged recovery candidates* — issues whose content reads as a question but
   were routed as ``missing_lesson`` and auto-rejected (dead end before the
   #1396 routing fix), or issues with an explicit ``kind=question`` that were
   auto-rejected by the pre-fix lesson auto-review;
2. *explicit-kind flips* — an issue that pinned ``**Kind:**`` to something other
   than ``missing_lesson`` and had it overridden by the detector anyway. The
   detector honours an explicit kind today, so this list is a tripwire for a
   regression in it (it mirrors ``workers/lib/utils.js``), not a finding
   generator. It used to sit *after* the ``--digest`` early return, so the one
   invocation CI makes never reached it and its warning had no consumer (#3835).

Outputs:
- JSONL rows per issue (``--out``); ``--from-jsonl`` reads them back for an
  offline re-audit, so a recorded run can be replayed and tested without the API;
- a markdown digest (``--digest``) that states how many rows were read, how many
  each check hit, and which checks actually ran — the digest is the CI gate's
  artifact, so "0 flagged" is printed next to the evidence that a check ran.

Exit status (the conclusion, not a side effect — see
``lessons/contrib/report-only-verification-script-cannot-be-a-gate-step.md``):

    0  ran, both checks clean
    2  could not run: malformed ``--from-jsonl`` input
    3  an explicit ``Kind:`` was auto-flipped — this run fails
    4  zero rows read — nothing was audited, which is not a pass (#3759)

Usage:
    python3 scripts/audit_intake_kinds.py --labels mcp-intake --out /tmp/intake_audit.jsonl
    python3 scripts/audit_intake_kinds.py --labels auto-rejected --state open --summary
    python3 scripts/audit_intake_kinds.py --from-jsonl /tmp/intake_audit.jsonl --digest

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

# The sentence `intake-kind-audit.yml` greps for. It is printed *only* when there is something to
# vouch for — a clean digest and a digest that could not look are different claims — and the exit
# status says the same thing independently, so the grep is a second signal and not the only one.
CLEAN_SENTENCE = "No flagged question/lesson misfiles found. ✅"
NOTHING_AUDITED = (
    "**Nothing was audited.** 0 rows were read, so this run found nothing because it looked at "
    "nothing — that is not a pass (#3759). Check the label/state filters (or the replay file) and "
    "the token that is supposed to list the issues."
)

# Exit statuses. main() returns one of these and nothing else, so a caller can act on the number.
EXIT_CLEAN = 0
EXIT_INPUT = 2    # --from-jsonl input could not be read: the audit did not run
EXIT_FLIP = 3     # an explicit Kind: was overridden by the detector (#3835)
EXIT_EMPTY = 4    # zero rows read: 0/0 is not a pass

# The row shape `--out` writes and `--from-jsonl` reads. A replayed row carries the verdict that was
# recorded for it; replay re-applies the checks to those rows and never re-runs the detector.
ROW_FIELDS = ("number", "state", "labels", "kind_body", "kind_detected", "auto_detected")


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


def audit_issue(issue: dict, infer_intake_kind) -> dict:
    """Turn one issue into an audit row, asking the detector what it would have decided.

    The detector is a parameter rather than a module import so the live path (issue → row) can be
    driven from a fixture, and so ``--from-jsonl`` can replay recorded rows without it.
    """
    parsed = parse_intake(issue)
    kind_det, auto = infer_intake_kind(
        kind=parsed["kind_body"], problem=parsed["problem"],
    )
    return {
        "number": issue["number"],
        "title": parsed["title"][:100],
        "state": issue["state"],
        "labels": sorted(l["name"] for l in issue.get("labels") or []),
        # "none" renders an absent **Kind:** — distinct from a submitted "missing_lesson".
        "kind_body": parsed["kind_body"] or "none",
        "kind_detected": kind_det,
        "auto_detected": auto,
        "problem_preview": parsed["problem"].replace("\n", " ")[:140],
    }


def load_rows(path: str) -> list[dict]:
    """Read rows written by ``--out`` back for an offline re-audit.

    Raises ``ValueError`` instead of skipping a line. A row that cannot be read is a row that would
    not be checked, and "the check ran but looked at less than you think" is the defect this file
    exists to end — so a malformed line fails the run rather than shortening it.
    """
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"{path}: no such file")
    rows: list[dict] = []
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{lineno}: not JSON ({e.msg})") from None
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{lineno}: expected an object, got {type(row).__name__}")
        missing = [k for k in ROW_FIELDS if k not in row]
        if missing:
            raise ValueError(f"{path}:{lineno}: missing field(s) {', '.join(missing)}")
        # These two decide the verdicts; a string "false" would read as true and flip a clean row.
        if not isinstance(row["auto_detected"], bool):
            raise ValueError(f"{path}:{lineno}: auto_detected must be true/false")
        if not isinstance(row["labels"], list):
            raise ValueError(f"{path}:{lineno}: labels must be a list")
        rows.append(row)
    return rows


def find_flagged(rows: list[dict]) -> list[tuple[dict, str]]:
    """Return open recovery candidates as (row, reason) pairs.

    - question-content-auto-rejected: content reads as a question but the
      pre-fix pipeline auto-rejected it as a lesson (dead end → salvage)
    - explicit-question-auto-rejected: kind=question issue auto-rejected
      before the #1396 routing fix
    - explicit-question-unlabeled: kind=question issue missing question labels
    """
    flagged = []
    for r in rows:
        ln = set(r["labels"])
        rejected = "auto-rejected" in ln
        if r["auto_detected"] and rejected:
            flagged.append((r, "question-content-auto-rejected"))
        elif r["kind_body"] == "question" and rejected:
            flagged.append((r, "explicit-question-auto-rejected"))
        elif r["kind_body"] == "question" and not ({"question"} & ln):
            flagged.append((r, "explicit-question-unlabeled"))
    return flagged


def is_explicit_kind(kind_body: str) -> bool:
    """True when the issue body pinned a kind the detector must not override.

    ``missing_lesson`` is excluded because the detector is *allowed* to re-route it to ``question``
    — that is #1396's fix, and live open intakes rely on it. ``none`` is how a row renders an
    *absent* ``**Kind:**``, and an absent kind is the other case auto-detection exists for. Treating
    ``none`` as explicit was a false-positive path in the old inline check: any Kind-less question
    would have been reported as "flipped" the moment the check started deciding an exit status.
    """
    kind = str(kind_body or "").strip().lower()
    return bool(kind) and kind not in ("none", "missing_lesson")


def find_flipped(rows: list[dict]) -> list[dict]:
    """Rows whose explicit, non-``missing_lesson`` kind was auto-detected anyway.

    Empty by construction against the current detector: :func:`infer_intake_kind` honours any
    explicit valid kind and only ever sets ``auto_detected`` for ``missing_lesson``/absent. That is
    the intended value — this is a tripwire for a regression in the mirror of
    ``workers/lib/utils.js``, and it is the only thing here that can fail the run (#3835).
    """
    return [r for r in rows
            if r.get("auto_detected") and is_explicit_kind(r.get("kind_body", ""))]


def render_flip_section(flipped: list[dict]) -> list[str]:
    """The finding the run fails on: an explicit ``Kind:`` the detector overrode."""
    return [
        f"## ⚠️ Explicit kinds that were auto-flipped: {len(flipped)}",
        "",
        "An issue that states its `Kind:` must keep it — the detector overriding that choice is the "
        "regression this audit exists to catch (#3835). **This run fails on these rows.**",
        "",
        "| Issue | `Kind:` in body | auto-detected as |",
        "|-------|-----------------|------------------|",
        *[f"| [#{r['number']}](https://github.com/Ikalus1988/MisakaNet/issues/{r['number']}) "
          f"| `{r['kind_body']}` | `{r['kind_detected']}` |" for r in flipped],
    ]


def render_misfile_section(flagged: list[tuple[dict, str]]) -> list[str]:
    """Recovery candidates from #1396 — open, question-shaped, routed or rejected as lessons."""
    return [
        f"## 🧭 Question-shaped intakes routed as lessons: {len(flagged)}",
        "",
        "Open intake issues whose content reads as a **question** but were routed/",
        "rejected as **lessons** (see #1396). Reconcile each like #1396/#1397:",
        "`Kind: question`, `[Question]` title, drop `auto-rejected`/`needs-salvage`,",
        "add `question`/`type:question`.",
        "",
        "| Issue | Reason | Title |",
        "|-------|--------|-------|",
        *[f"| [#{r['number']}](https://github.com/Ikalus1988/MisakaNet/issues/{r['number']}) "
          f"| {why} | {r['title'][:70]} |" for r, why in flagged],
    ]


def render_scope(rows: list[dict], flagged: list[tuple[dict, str]], flipped: list[dict],
                 source: str) -> list[str]:
    """What this run actually read and executed (#3759).

    A digest that reports findings without its denominator cannot be distinguished from one that
    examined nothing, so the counts of *what ran* belong next to the verdict, not in a log line.
    """
    allowed = sum(1 for r in rows
                  if r.get("auto_detected") and not is_explicit_kind(r.get("kind_body", "")))
    return [
        "---",
        f"**Audit scope** — {source}. {len(rows)} row(s) read; `find_flagged` over the open row(s) "
        f"→ {len(flagged)} flagged; explicit-kind flip cross-check over all {len(rows)} row(s) "
        f"→ {len(flipped)} flipped ({allowed} row(s) auto-detected from an absent or "
        "`missing_lesson` kind, which is allowed).",
        "Checks that ran in this invocation: `find_flagged`, `find_flipped`, digest render. "
        "Nothing was written to GitHub.",
    ]


def render_digest(flagged: list[tuple[dict, str]], *, rows: list[dict] | None = None,
                  flipped: list[dict] | None = None, source: str = "") -> str:
    """Markdown digest of everything the audit found, plus what it examined.

    ``rows=None`` means "scope unknown" (older callers, tests): the clean sentence is printed and
    no scope footer is added. When rows *are* known, an empty corpus prints :data:`NOTHING_AUDITED`
    instead — the one case where the digest must not say "clean".
    """
    flipped = list(flipped or [])
    checked = None if rows is None else len(rows)
    lines: list[str] = []
    if flipped or flagged:
        lines += ["# 🧭 Intake Kind Audit", ""]
        if flipped:
            lines += render_flip_section(flipped)
            lines.append("")
        if flagged:
            lines += render_misfile_section(flagged)
            lines.append("")
    elif checked == 0:
        lines += [NOTHING_AUDITED, ""]
    else:
        lines += [CLEAN_SENTENCE, ""]
    if rows is not None:
        lines += render_scope(rows, flagged, flipped, source)
        lines.append("")
    if flipped or flagged:
        lines += ["_Automated weekly audit (read-only). No labels/issues were changed._"]
    return "\n".join(lines).rstrip()


def exit_status(rows: list[dict], flipped: list[dict]) -> int:
    """The conclusion: 0 only when the checks ran over something and found nothing."""
    if flipped:
        return EXIT_FLIP
    if not rows:
        return EXIT_EMPTY
    return EXIT_CLEAN


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default="mcp-intake",
                    help="comma-separated labels (default: mcp-intake); ignored by --from-jsonl")
    ap.add_argument("--state", default="all", choices=["open", "closed", "all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="", help="JSONL output path (default: stdout)")
    ap.add_argument("--from-jsonl", default="", metavar="PATH",
                    help="audit rows written by --out instead of calling the API (offline replay; "
                         "labels/state/limit are ignored and the detector is not re-run)")
    ap.add_argument("--summary", action="store_true", help="print summary table only")
    ap.add_argument("--digest", action="store_true",
                    help="print the markdown digest (cron/CI mode). Exits 3 on a flipped explicit "
                         "kind and 4 when nothing was read, so the digest is a gate and not a report")
    args = ap.parse_args(argv)

    if args.from_jsonl:
        try:
            rows = load_rows(args.from_jsonl)
        except (OSError, ValueError) as e:
            print(f"audit_intake_kinds: replay not read: {e}", file=sys.stderr)
            return EXIT_INPUT
        source = f"replay of `{args.from_jsonl}` (no API call, no re-inference)"
        print(f"replayed {len(rows)} rows from {args.from_jsonl}", file=sys.stderr)
    else:
        from scripts.intake_kind import infer_intake_kind  # local import: repo path

        labels = [l.strip() for l in args.labels.split(",") if l.strip()]
        issues = fetch_issues(labels, args.state, args.limit)
        print(f"fetched {len(issues)} issues (labels={labels}, state={args.state})",
              file=sys.stderr)
        rows = [audit_issue(issue, infer_intake_kind) for issue in issues]
        source = f"GitHub API `{REPO}` · labels `{','.join(labels)}` · state `{args.state}`"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        # stderr: --out may be combined with --digest, whose stdout is the CI artifact.
        print(f"wrote {len(rows)} rows -> {args.out}", file=sys.stderr)

    # ── both checks, before any mode can return ────────────────────────────────────────────────
    # They used to sit after the `--digest` return, and `--digest` is the only invocation CI makes:
    # the flip check was dead code and its warning had no reader (#3835).
    flipped = find_flipped(rows)

    if args.digest:
        # The digest is about open recovery candidates; the flip cross-check covers every row it
        # read, because an overridden kind is a detector regression whether or not the issue is open.
        open_rows = [r for r in rows if r["state"] == "open"]
        flagged = find_flagged(open_rows)
        print(render_digest(flagged, rows=rows, flipped=flipped, source=source))
    else:
        if (args.summary or not args.out):
            print(f"\n{'#':>4} {'state':<6} {'kind_body':<20} {'detected':<14} {'auto':<5} labels")
            for r in rows:
                auto = "Y" if r["auto_detected"] else ""
                print(f"{r['number']:>4} {r['state']:<6} {r['kind_body']:<20} "
                      f"{r['kind_detected']:<14} {auto:<5} {','.join(x for x in r['labels'] if x in ('auto-rejected','needs-salvage','question','type:question','test','needs-human-review','pending-review'))}")

        # ── flagged recovery candidates (interactive) ──
        flagged = find_flagged(rows)
        if flagged:
            print(f"\n== {len(flagged)} flagged recovery candidates ==")
            for r, why in flagged:
                print(f"#{r['number']} [{why}] {r['state']} {r['title']}")
                print(f"    problem: {r['problem_preview']}")
        else:
            print("\n== no flagged recovery candidates ==")

    # ── the failure signal: the exit status, not only a warning line ───────────────────────────
    status = exit_status(rows, flipped)
    if flipped:
        print(f"\nFAIL: {len(flipped)} explicit Kind(s) were auto-flipped — this run exits "
              f"{EXIT_FLIP}:", file=sys.stderr)
        for r in flipped:
            print(f"  #{r['number']} kind_body={r['kind_body']} -> {r['kind_detected']}",
                  file=sys.stderr)
    elif status == EXIT_EMPTY:
        where = (f"replay of {args.from_jsonl}" if args.from_jsonl
                 else f"labels={args.labels}, state={args.state}")
        print(f"FAIL: 0 rows audited ({where}) — nothing was vouched for, this run exits "
              f"{EXIT_EMPTY}.", file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    sys.exit(main())
