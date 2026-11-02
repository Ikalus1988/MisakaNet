#!/usr/bin/env python3
"""Emit intake conversion receipts when contributed lessons are published.

When an intake (submitted via misakanet_submit_intake) gets promoted to a
published lesson, this script:
1. Scans all published lessons for `contrib_id` in frontmatter
2. Checks against a receipt log to find new promotions
3. Posts a GitHub comment on the original intake issue with the lesson details
4. Records the receipt to prevent duplicate notifications

Usage:
    python3 scripts/emit_intake_receipt.py              # scan and emit
    python3 scripts/emit_intake_receipt.py --dry-run    # preview only
    python3 scripts/emit_intake_receipt.py --check      # verify no pending receipts

Requires GH_TOKEN for posting comments (uses gh CLI).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
RECEIPT_LOG = REPO / "data" / "intake_receipts.jsonl"

# gh accepts an issue by number (with --repo) or by full URL — NOT by the
# "owner/repo#number" shorthand, which fails with `invalid issue format`
# (measured against gh 2.102.0, 2026-10-04).  We pass a full URL so the
# command works without also threading --repo through.
GITHUB_REPO_SLUG = "Ikalus1988/MisakaNet"
ISSUES_URL_BASE = f"https://github.com/{GITHUB_REPO_SLUG}/issues"

# Frontmatter parser (inline to avoid heavy imports)
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    """Extract frontmatter as a dict. Supports JSON and YAML."""
    m = _FM_RE.match(text)
    if not m:
        return {}
    raw = m.group(1).strip()
    try:
        fm = json.JSONDecoder().raw_decode(raw)[0]
        if isinstance(fm, dict):
            return fm
    except json.JSONDecodeError:
        pass
    try:
        import yaml
        fm = yaml.safe_load(raw)
        if isinstance(fm, dict):
            return fm
    except Exception:
        pass
    return {}


def _issue_from_provenance(fm: dict) -> str:
    """The issue number a lesson cites, as a string, or "" — from `provenance.issue`.

    Accepts `"#4249"`, `"#4146 + #4157"` (the converter's merged form) and a bare number. A merged
    lesson cites the *first* issue for the receipt: one receipt per issue is the contract, and the
    second intake is named in the case rather than in the log.
    """
    provenance = fm.get("provenance")
    value = ""
    if isinstance(provenance, dict):
        value = str(provenance.get("issue") or "")
    if not value:
        value = str(fm.get("provenance_issue") or "")
    match = re.search(r"#?(\d{1,7})", value)
    return match.group(1) if match else ""


def _load_receipts() -> set[str]:
    """Load set of contrib_ids that already received receipts."""
    if not RECEIPT_LOG.exists():
        return set()
    ids = set()
    for line in RECEIPT_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entry = json.loads(line)
                ids.add(entry.get("contrib_id", ""))
            except json.JSONDecodeError:
                continue
    return ids


def _append_receipt(contrib_id: str, lesson_path: str, issue_url: str, evidence_level: str) -> None:
    """Append a receipt entry to the log."""
    import datetime
    entry = {
        "contrib_id": contrib_id,
        "lesson_path": lesson_path,
        "issue_url": issue_url,
        "evidence_level": evidence_level,
        "emitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    RECEIPT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RECEIPT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _scan_published_lessons() -> list[dict]:
    """Scan all published lessons (not drafts) for contrib_id in frontmatter."""
    results = []
    skip_files = {"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"}

    for subdir in ("core", "contrib", "en"):
        d = LESSONS_DIR / subdir
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            if md.name in skip_files:
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            fm = _parse_frontmatter(text)
            contrib_id = fm.get("contrib_id", "")
            if not contrib_id:
                # `provenance.issue: "#4249"` is what the intake converter writes; `contrib_id` is
                # what this script was written to look for, and **no lesson has ever carried it**
                # (measured 2026-11-02: 0 lessons with `contrib_id`, 330 with `provenance.issue`).
                # So the daily "Emit intake receipts" step in `update-lessons.yml` had been a no-op
                # since it was added, and every receipt posted until now was posted by hand.
                contrib_id = _issue_from_provenance(fm)
            if not contrib_id:
                continue
            # Skip drafts
            status = fm.get("status", "")
            if status == "draft":
                continue
            results.append({
                "contrib_id": contrib_id,
                "lesson_path": str(md.relative_to(REPO)),
                "title": fm.get("title", md.stem),
                "domain": fm.get("domain", ""),
                "evidence_level": fm.get("evidence_level", "unverified"),
                "source": fm.get("source", ""),
            })
    return results


def _post_issue_comment(issue_url: str, body: str) -> bool:
    """Post a comment on a GitHub issue using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "issue", "comment", issue_url, "--body", body],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _format_receipt_message(lesson: dict) -> str:
    """Format the receipt comment body."""
    return (
        f"🎉 **Your intake has been published as a lesson!**\n\n"
        f"- **Lesson:** [{lesson['title']}]({lesson['lesson_path']})\n"
        f"- **Domain:** {lesson['domain']}\n"
        f"- **Evidence level:** {lesson['evidence_level']}\n"
        f"- **Source:** {lesson['source']}\n\n"
        f"Thank you for contributing to MisakaNet! "
        f"Your submission helped build the shared knowledge base."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit intake conversion receipts.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--check", action="store_true", help="Exit 1 if pending receipts exist")
    parser.add_argument("--quiet", action="store_true", help="Silent on success")
    parser.add_argument("--close", action="store_true",
                        help="Close the intake issue after a receipt is posted (the conversion is "
                             "the resolution; a receipt nobody closes leaves the queue looking full)")
    parser.add_argument("--seed-log", action="store_true",
                        help="Record every current lesson↔issue pair WITHOUT posting anything. Run "
                             "once before enabling the daily job on a corpus that already has "
                             "hundreds of converted intakes, otherwise the first run posts a receipt "
                             "for every lesson ever written.")
    args = parser.parse_args(argv)

    # Scan for published lessons with contrib_id
    published = _scan_published_lessons()
    already_receipted = _load_receipts()

    # Find new promotions
    pending = [l for l in published if l["contrib_id"] not in already_receipted]

    if args.seed_log:
        for lesson in pending:
            _append_receipt(lesson["contrib_id"], lesson["lesson_path"],
                            _resolve_issue_url(lesson["contrib_id"]) or "", lesson["evidence_level"])
        print(f"seeded {len(pending)} lesson↔issue pair(s); nothing was posted and no issue closed")
        return 0

    if args.check:
        if pending:
            print(f"❌ {len(pending)} intake(s) pending receipt:", file=sys.stderr)
            for l in pending[:10]:
                print(f"  {l['contrib_id']}: {l['title']} ({l['lesson_path']})", file=sys.stderr)
            return 1
        if not args.quiet:
            print("✅ All intake receipts are up to date")
        return 0

    if not pending:
        if not args.quiet:
            print("✅ No pending intake receipts")
        return 0

    # Emit receipts
    emitted = 0
    failed: list[str] = []
    for lesson in pending:
        contrib_id = lesson["contrib_id"]
        # Find the intake issue — contrib_id format is typically the GitHub issue number
        # or a unique ID from the contribution queue
        issue_url = _resolve_issue_url(contrib_id)

        if args.dry_run:
            print(f"  DRY RUN: would post receipt for {contrib_id} -> {lesson['lesson_path']}")
            if issue_url:
                print(f"    Issue: {issue_url}")
            continue

        # Post comment if we have an issue URL
        success = False
        if issue_url:
            body = _format_receipt_message(lesson)
            success = _post_issue_comment(issue_url, body)

        if success or not issue_url:
            _append_receipt(contrib_id, lesson["lesson_path"], issue_url or "", lesson["evidence_level"])
            emitted += 1
        else:
            # Deliberately NOT recorded.  The contributor was never told, so the
            # obligation is still outstanding; recording it here marks the receipt
            # delivered and it is then skipped forever (measured 2026-10-04: every
            # post failed on a bad issue reference while still being logged).
            failed.append(contrib_id)

        if success:
            closed = _close_issue(issue_url) if args.close else False
            print(f"  ✅ Receipt posted for {contrib_id} -> {lesson['lesson_path']}"
                  + (" (issue closed)" if closed else ""))
        elif issue_url:
            print(f"  ⚠️  Comment FAILED for {contrib_id} — not recorded, retried next run")
        else:
            print(f"  ℹ️  Receipt recorded (no issue URL) for {contrib_id}")

    if failed:
        # Loud, but NOT a non-zero exit: this step sits ahead of the regeneration
        # steps in the single `update` job, so failing here would freeze the daily
        # pipeline over one owed comment.  A warning annotation keeps it visible in
        # the run summary while the next scheduled run retries.
        print(
            f"::warning title=Intake receipts undelivered::"
            f"{len(failed)} receipt(s) could not be posted and were NOT recorded: "
            f"{', '.join(failed[:10])}. They will be retried on the next run.",
            file=sys.stderr,
        )
        print(
            f"⚠️  {len(failed)} intake receipt(s) undelivered — see the run warning",
            file=sys.stderr,
        )

    if not args.quiet and not args.dry_run:
        print(f"\n✅ Emitted {emitted} intake receipt(s)")

    return 0


def _close_issue(issue_url: str) -> bool:
    """Close an intake whose lesson has been published. Failure is not fatal: the receipt is the
    obligation, the close is bookkeeping."""
    out = subprocess.run(["gh", "issue", "close", issue_url, "--reason", "completed"],
                         capture_output=True, text=True)
    return out.returncode == 0


def _resolve_issue_url(contrib_id: str) -> str | None:
    """Try to resolve a contrib_id to a GitHub issue URL.

    contrib_id formats:
    - "mcp-<timestamp>" — no issue to comment on
    - "intake-<hash>" — from contribution queue, may have issue
    - "<number>" — direct GitHub issue number
    """
    # Direct issue number
    if contrib_id.isdigit():
        return f"{ISSUES_URL_BASE}/{contrib_id}"

    # Check if there's an issue in the contribution queue entry
    queue_path = REPO / "data" / "contribution_queue.jsonl"
    if queue_path.exists():
        for line in queue_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line.strip())
                if entry.get("id") == contrib_id or entry.get("source_id") == contrib_id:
                    issue_num = entry.get("issue_number") or entry.get("github_issue")
                    if issue_num:
                        return f"{ISSUES_URL_BASE}/{issue_num}"
            except json.JSONDecodeError:
                continue

    return None


if __name__ == "__main__":
    raise SystemExit(main())