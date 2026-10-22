#!/usr/bin/env python3
"""Post the conversion receipt for each done-but-open intake, and label it `ready-to-close` (#3509).

Why this exists
---------------
`scripts/done_but_open.py` finds the intakes whose lesson is already on `main` while the issue is
still open, and `scripts/intake_receipt.py` composes the receipt. Every morning the digest reports
them and nothing else happens: measured 2026-10-18, 20 of the 26 issues closed that day were
exactly this class — lesson merged days earlier, issue open, reporter never told. Median intake
cycle time 3.2 days, p90 15.1. SOP §3 makes the receipt an iron rule; a rule that depends on
somebody remembering is not a mechanism, so this is the mechanism's posting half.

What this file is deliberately *not*
-----------------------------------
It is **glue**, not a second resolver. Whether "this intake was converted" is answered by
`scripts/intake_receipt.lessons_citing`, which reads the shapes contributors actually write
(`source: intake-1130`, `provenance.issue: "#1130"`, a full issue link) and refuses a bare `#N`
in prose — the 2026-09-22 lesson where a forum URL, a blog archive year and a date matched three
intakes that had never been heard of. That answer is re-run against the **current tree** at post
time, so a finding whose lesson was reverted or removed gets no receipt rather than a stale one.

It never closes an issue: closing stays a human act (`docs/maintainer/intake-triage.md` §2 — the
auto-rejected-noise rule exists for the same reason). It applies `ready-to-close` so the human
knows the work is done and told, and it leaves `needs-human-review` alone.

Idempotent posting
-----------------
The comment body carries `<!-- misakanet-receipt -->`. A re-run finds that marker and **edits**
the existing comment instead of adding a second one, so "running the digest twice" leaves exactly
one receipt per finding.

    python3 scripts/post_intake_receipts.py --post --findings /tmp/done_but_open.json
    python3 scripts/post_intake_receipts.py --post --issue 1472
    python3 scripts/post_intake_receipts.py --issue 1472            # dry-run: print, write nothing

The scheduled caller is `intake-salvage-digest.yml`, which feeds this the findings JSON that the
`done_but_open.py --json-out` step already wrote — one listing pass of the open backlog per run,
not two.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# The single resolver. Do not re-derive citation shapes here — see the module docstring.
from scripts.intake_receipt import compose, lessons_citing, render  # noqa: E402

RECEIPT_MARKER = "<!-- misakanet-receipt -->"
READY_TO_CLOSE = "ready-to-close"
#: Page cap for list reads — a proxy that strips `page` must not make us loop forever. Same bound
#: as `workers_builds_watch.MAX_LIST_PAGES`, for the same reason.
MAX_LIST_PAGES = 10
LABEL_COLOR = "0e8a16"
LABEL_DESCRIPTION = ("Lesson is on main and the reporter has been receipted; "
                     "a human can close this.")


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class GitHub:
    """The four issue operations this step needs. `request` is injectable so tests can fake it."""

    def __init__(self, token: str | None, repo: str | None = None, request=None):
        self.token = token
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")
        self._request = request or self._http

    def _http(self, method: str, path: str, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.github.com{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise ApiError(exc.code, f"{method} {path}: {exc.code} {detail}") from exc

    def list_comments(self, issue: int) -> list:
        """Every comment on the issue, not just the first page.

        GitHub returns comments **oldest first**, so one `per_page=100` page is the oldest 100 and
        the receipt comment — typically the newest — is exactly the one that goes missing past the
        cliff, which would make a re-run post a second receipt and break AC1 in the one case it is
        meant to cover. Measured in this repository: #2020 carries 249 comments. Bounded by
        `MAX_LIST_PAGES` so a proxy that strips `page` cannot loop forever (same reason as
        `workers_builds_watch.all_issue_comments`).
        """
        collected: list = []
        for page in range(1, MAX_LIST_PAGES + 1):
            batch = self._request(
                "GET", f"/repos/{self.repo}/issues/{int(issue)}/comments?per_page=100&page={page}")
            batch = batch or []
            collected.extend(batch)
            if len(batch) < 100:
                break
        return collected

    def create_comment(self, issue: int, body: str) -> dict:
        return self._request("POST", f"/repos/{self.repo}/issues/{int(issue)}/comments", {"body": body})

    def update_comment(self, comment_id: int, body: str) -> dict:
        return self._request("PATCH", f"/repos/{self.repo}/issues/comments/{int(comment_id)}", {"body": body})

    def ensure_label(self, name: str) -> None:
        try:
            self._request("POST", f"/repos/{self.repo}/labels",
                          {"name": name, "color": LABEL_COLOR, "description": LABEL_DESCRIPTION})
        except ApiError as exc:
            # 422 "already exists" is the normal second-run case and must not fail the step.
            if exc.status != 422:
                raise

    def add_labels(self, issue: int, labels) -> None:
        # Additive: never removes `needs-human-review` or anything else already on the issue.
        self._request("POST", f"/repos/{self.repo}/issues/{int(issue)}/labels", {"labels": list(labels)})


#: SOP §3 point 5 — the anonymous MCP reporter has no GitHub thread to be notified in, so the
#: comment has to name the channel they can actually use: `misakanet_register` with the same
#: `client_id` returns the same node, and the receipt is waiting there.
CHANNEL_NOTE = (
    "**回执渠道**：匿名 MCP 报料者收不到 GitHub 通知——本条公开留档。"
    "用与提交时**同一个 `client_id`** 调用 `misakanet_register` 可注册回执通道；"
    "之后用相同 problem 文本重新 `submit_intake`（或 `misakanet_me_inbox`）即可取回本回执。"
)


def comment_body(receipt: dict) -> str:
    """The comment to post: the generated receipt (intake_receipt.render) plus the idempotency
    marker and the receipt-channel sentence AC3 asks for."""
    return "\n".join([
        RECEIPT_MARKER,
        render(receipt),
        "",
        CHANNEL_NOTE,
        "",
    ])


def receipt_for(intake: int, source: str = "unknown", lessons_dir: Path | None = None) -> dict:
    """Resolve the citation through the SSOT against the *current* tree.

    `lessons_dir` is the test seam: production reads the repository's `lessons/`, tests point it
    at a fixture tree. Either way the decision is `intake_receipt`'s, not this file's.
    """
    if lessons_dir is None:
        return compose(intake, source)
    return compose(intake, source, lessons=lessons_citing(intake, lessons_dir))


def post_finding(finding, gh, *, source: str = "unknown", lessons_dir: Path | None = None,
                 dry_run: bool = False) -> dict:
    """Post (or update) one receipt and apply `ready-to-close`. Never closes.

    Returns a result dict so the caller — and the two-run test — can see exactly what happened.
    """
    intake = int(finding["intake"])
    receipt = receipt_for(intake, source, lessons_dir)
    if not receipt["emitted"]:
        # AC2/AC4: no frontmatter citation, or the lesson was reverted/removed since the finding
        # was listed. Nothing to say, so nothing is written: no comment, no label.
        return {"intake": intake, "action": "skipped", "posts": 0,
                "reason": receipt.get("reason", "no lesson cites"), "labels": []}

    body = comment_body(receipt)
    if dry_run:
        return {"intake": intake, "action": "would-upsert", "posts": 0, "body": body,
                "lessons": [l["id"] for l in receipt["lessons"]],
                "evidence_level": receipt.get("evidence_level"), "labels": []}

    existing = next((c for c in gh.list_comments(intake)
                     if RECEIPT_MARKER in (c.get("body") or "")), None)
    if existing is not None:
        # AC1: a re-run *edits* rather than duplicates.
        comment = gh.update_comment(existing["id"], body)
        action = "edited"
    else:
        comment = gh.create_comment(intake, body)
        action = "created"
    gh.ensure_label(READY_TO_CLOSE)
    gh.add_labels(intake, [READY_TO_CLOSE])
    return {"intake": intake, "action": action, "posts": 1,
            "comment_id": (comment or {}).get("id"),
            "lessons": [l["id"] for l in receipt["lessons"]],
            "evidence_level": receipt.get("evidence_level"),
            "labels": [READY_TO_CLOSE]}


def format_result(result: dict) -> str:
    intake = result.get("intake")
    action = result.get("action")
    if action == "skipped":
        return f"- #{intake}: skipped — {result.get('reason', '')}"
    lessons = ", ".join(result.get("lessons") or [])
    level = result.get("evidence_level") or "未标注"
    label = f" + labeled {READY_TO_CLOSE}" if result.get("labels") else ""
    comment = f"comment {result['comment_id']}" if result.get("comment_id") else "comment"
    if action == "would-upsert":
        return f"- #{intake}: would upsert receipt ({lessons}, {level})"
    return f"- #{intake}: {action} {comment} ({lessons}, {level}){label}"


def _load_findings(args) -> tuple[list, bool]:
    """(findings, explicitly_requested). An explicitly empty list stays empty — it must not
    trigger a second listing of the open backlog just because `[]` is falsy."""
    findings = []
    explicit = False
    if args.findings:
        explicit = True
        if not args.findings.is_file():
            raise SystemExit(f"findings file not found: {args.findings} "
                             "(the done_but_open.py step writes it before this one runs)")
        findings = json.loads(args.findings.read_text(encoding="utf-8"))
    if args.issue:
        explicit = True
        findings += [{"intake": n} for n in args.issue]
    return findings, explicit


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="post conversion receipts + ready-to-close, once per finding (#3509)")
    parser.add_argument("--post", action="store_true",
                        help="actually post/label (without it: dry-run, print only)")
    parser.add_argument("--findings", type=Path, metavar="PATH",
                        help="findings JSON from scripts/done_but_open.py --json-out")
    parser.add_argument("--issue", type=int, action="append",
                        help="one intake to handle (repeatable)")
    parser.add_argument("--source", default="unknown",
                        help="the reporter's source label, if known")
    args = parser.parse_args(argv)

    findings, explicit = _load_findings(args)
    if not explicit:
        # No `--findings`/`--issue`: fall back to asking the existing detector — one more listing
        # of the backlog, only on this standalone path (the workflow always passes the JSON).
        from scripts.done_but_open import _token, findings as detect, open_issue_numbers
        findings = detect(open_issue_numbers(_token()))

    gh = None
    if args.post:
        from scripts.done_but_open import _token
        token = _token()
        if not token:
            print("no GitHub token: set GITHUB_TOKEN or GH_TOKEN to use --post", file=sys.stderr)
            return 2
        gh = GitHub(token)

    results = []
    failed = []
    for finding in findings:
        try:
            result = post_finding(finding, gh, source=args.source, dry_run=not args.post)
        except Exception as exc:  # one bad issue must not abandon the rest
            failed.append(f"#{finding.get('intake')}: {exc}")
            result = {"intake": finding.get("intake"), "action": "failed", "posts": 0,
                      "reason": str(exc), "labels": []}
        results.append(result)
        print(format_result(result))

    posted = sum(r.get("posts", 0) for r in results)
    skipped = sum(1 for r in results if r.get("action") == "skipped")
    print(f"\n{posted} receipt(s) posted/updated, {skipped} skipped, {len(failed)} failed.")
    if failed:
        print("failures:", file=sys.stderr)
        for line in failed:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
