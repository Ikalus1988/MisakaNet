#!/usr/bin/env python3
"""Intake conversion receipt engine.

Closes the feedback loop between external intake submissions and published lessons.
When an intake is promoted to a published lesson, emits a conversion receipt
(comment, webhook, and ledger record) containing evidence_level and lesson details.

Usage:
    python3 scripts/intake_receipt.py --scan
    python3 scripts/intake_receipt.py --emit [--dry-run] [--channels comment,webhook,ledger]
    python3 scripts/intake_receipt.py --manual --source <src> --issue <num> --lesson <id> --evidence <level> [--title <title>] [--dry-run]
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.source_ledger import (
    is_receipt_emitted,
    record_promotion,
    record_receipt,
    LEDGER_PATH,
)

LESSONS_JSON_FILE = REPO_ROOT / "data" / "lessons.json"
DEFAULT_REPO = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def build_receipt(
    source: str = None,
    intake_issue: int | str = None,
    lesson_id: str = None,
    lesson_title: str = "",
    evidence_level: str = "E0",
    lesson_url: str = None,
    domain: str = None,
    extra: dict = None,
    title: str = "",
    **kwargs,
) -> dict:
    """Construct a standardized intake conversion receipt."""
    clean_source = str(source).strip() if source else "unknown"
    clean_lesson_id = str(lesson_id).strip() if lesson_id else ""
    intake_num = None
    if intake_issue is not None:
        digits = re.findall(r"\d+", str(intake_issue))
        intake_num = int(digits[0]) if digits else None

    issue_label = f"#{intake_num}" if intake_num else str(intake_issue or "")
    receipt_id = f"rcpt-{intake_num or 'anon'}-{clean_lesson_id}"
    url = lesson_url or f"https://misakanet.org/lessons/{clean_lesson_id}/"
    effective_title = lesson_title or title or clean_lesson_id

    receipt = {
        "receipt_id": receipt_id,
        "source": clean_source,
        "intake_issue": intake_num,
        "intake_label": issue_label,
        "intake_url": f"https://github.com/{DEFAULT_REPO}/issues/{intake_num}" if intake_num else "",
        "lesson_id": clean_lesson_id,
        "lesson_title": effective_title,
        "lesson_url": url,
        "evidence_level": evidence_level or "E0",
        "domain": domain or "general",
        "status": "promoted",
        "emitted_at": _now_iso(),
    }
    if extra:
        receipt.update(extra)
    return receipt


def format_receipt_markdown(receipt: dict) -> str:
    """Format conversion receipt as a clean Markdown issue comment without emojis."""
    lines = [
        "### Intake Conversion Receipt",
        "",
        f"Your intake contribution **{receipt.get('intake_label', '')}** has been promoted to an official MisakaNet lesson.",
        "",
        "| Field | Value |",
        "| :--- | :--- |",
        f"| **Lesson ID** | `{receipt['lesson_id']}` |",
        f"| **Title** | {receipt.get('lesson_title', receipt['lesson_id'])} |",
        f"| **Evidence Level** | `{receipt.get('evidence_level', 'E0')}` |",
        f"| **Lesson URL** | [{receipt['lesson_id']}]({receipt['lesson_url']}) |",
        f"| **Receipt ID** | `{receipt['receipt_id']}` |",
        "",
        "---",
        "> MisakaNet Intake Conversion Engine — closing the loop for automated and community contributors.",
    ]
    return "\n".join(lines)


def format_receipt_webhook_payload(receipt: dict) -> dict:
    """Format structured JSON payload for external webhooks."""
    return {
        "event": "intake_promoted",
        "receipt_id": receipt["receipt_id"],
        "source": receipt["source"],
        "intake_issue": receipt.get("intake_issue"),
        "intake_url": receipt.get("intake_url"),
        "lesson": {
            "id": receipt["lesson_id"],
            "title": receipt["lesson_title"],
            "url": receipt["lesson_url"],
            "evidence_level": receipt["evidence_level"],
            "domain": receipt.get("domain", "general"),
        },
        "evidence_level": receipt["evidence_level"],
        "status": "promoted",
        "timestamp": receipt["emitted_at"],
    }


def emit_receipt_comment(
    intake_issue: int | str,
    comment_body: str,
    repo: str = None,
    dry_run: bool = False,
) -> bool:
    """Post receipt comment to GitHub issue."""
    digits = re.findall(r"\d+", str(intake_issue))
    if not digits:
        return False
    issue_num = int(digits[0])
    target_repo = repo or DEFAULT_REPO

    if dry_run:
        print(f"[DRY-RUN] Would post comment to {target_repo}#{issue_num}:\n{comment_body}")
        return True

    gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not gh_token:
        try:
            import subprocess
            proc = subprocess.run(
                ["gh", "issue", "comment", str(issue_num), "--repo", target_repo, "--body", comment_body],
                capture_output=True,
                text=True,
                check=False,
            )
            return proc.returncode == 0
        except Exception as e:
            print(f"Failed to call gh cli: {e}", file=sys.stderr)
            return False

    api_url = f"https://api.github.com/repos/{target_repo}/issues/{issue_num}/comments"
    req = urllib.request.Request(
        api_url,
        data=json.dumps({"body": comment_body}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MisakaNet-Intake-Receipt/1.0",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"Failed to post comment to issue {issue_num}: {e}", file=sys.stderr)
        return False


def emit_receipt_webhook(
    receipt: dict,
    webhook_url: str = None,
    dry_run: bool = False,
) -> bool:
    """Send conversion receipt to external webhook."""
    target_url = webhook_url or os.environ.get("INTAKE_RECEIPT_WEBHOOK_URL") or os.environ.get("FEISHU_WEBHOOK_URL")
    if not target_url:
        return False

    payload = format_receipt_webhook_payload(receipt)
    if dry_run:
        print(f"[DRY-RUN] Would POST to webhook {target_url}:\n{json.dumps(payload, indent=2)}")
        return True

    req = urllib.request.Request(
        target_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "MisakaNet-Intake-Receipt/1.0",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201, 202, 204)
    except Exception as e:
        print(f"Failed to emit webhook to {target_url}: {e}", file=sys.stderr)
        return False


def emit_conversion_receipt(
    receipt: dict = None,
    channels: list[str] = None,
    dry_run: bool = False,
    repo: str = None,
    ledger_path: Path | str = None,
    source: str = None,
    intake_issue: int | str = None,
    lesson_id: str = None,
    lesson_title: str = "",
    evidence_level: str = "E0",
    title: str = "",
    **kwargs,
) -> dict:
    """Emit a conversion receipt across requested channels."""
    active_channels = channels or ["comment", "webhook", "ledger"]
    results = {}

    if receipt is None:
        receipt = build_receipt(
            source=source,
            intake_issue=intake_issue,
            lesson_id=lesson_id,
            lesson_title=lesson_title or title or (lesson_id or ""),
            evidence_level=evidence_level,
        )

    source = receipt["source"]
    lesson_id = receipt["lesson_id"]
    intake_issue = receipt.get("intake_issue")
    evidence_level = receipt.get("evidence_level", "E0")
    title = receipt.get("lesson_title", lesson_id)
    url = receipt.get("lesson_url")
    receipt_id = receipt["receipt_id"]

    if not dry_run and is_receipt_emitted(source, intake_issue, lesson_id, path=ledger_path):
        return {"emitted": False, "skipped": True, "reason": "Already emitted", "receipt": receipt}

    if "comment" in active_channels and intake_issue:
        comment_body = format_receipt_markdown(receipt)
        comment_ok = emit_receipt_comment(intake_issue, comment_body, repo=repo, dry_run=dry_run)
        results["comment"] = comment_ok

    if "webhook" in active_channels:
        webhook_ok = emit_receipt_webhook(receipt, dry_run=dry_run)
        results["webhook"] = webhook_ok

    if "ledger" in active_channels and not dry_run:
        record_promotion(
            source=source,
            lesson_id=lesson_id,
            intake_issue=intake_issue,
            evidence_level=evidence_level,
            title=title,
            url=url,
            path=ledger_path,
        )
        record_receipt(
            source=source,
            receipt_id=receipt_id,
            channel=",".join(c for c in active_channels if c != "ledger"),
            intake_issue=intake_issue,
            lesson_id=lesson_id,
            path=ledger_path,
        )
        results["ledger"] = True
    elif dry_run:
        results["ledger"] = True

    results["emitted"] = True
    results["dry_run"] = dry_run
    results["receipt"] = receipt
    return results


def scan_promotions(
    repo_root: Path = None,
    ledger_path: Path | str = None,
    lessons_path: Path | str = None,
) -> list[dict]:
    """Scan lessons for intakes that need conversion receipts."""
    lessons_file = Path(lessons_path) if lessons_path else ((repo_root or REPO_ROOT) / "data" / "lessons.json")
    if not lessons_file.exists():
        return []

    try:
        lessons = json.loads(lessons_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    pending = []
    for lesson in lessons:
        source = lesson.get("source")
        intake_issue = lesson.get("intake_issue")
        lesson_id = lesson.get("id")

        if not lesson_id or not intake_issue or not source:
            continue

        if is_receipt_emitted(source, intake_issue, lesson_id, ledger_path):
            continue

        receipt = build_receipt(
            source=source,
            intake_issue=intake_issue,
            lesson_id=lesson_id,
            lesson_title=lesson.get("title", lesson_id),
            evidence_level=lesson.get("evidence_level", "E0"),
            lesson_url=f"https://misakanet.org/{lesson.get('url', f'lessons/{lesson_id}/')}",
            domain=lesson.get("domain", "general"),
        )
        pending.append(receipt)

    return pending


def run_pipeline(
    channels: list[str] = None,
    dry_run: bool = False,
    repo_root: Path = None,
    ledger_path: Path | str = None,
) -> list[dict]:
    """Scan and emit conversion receipts for all unreceipted promoted intakes."""
    pending = scan_promotions(repo_root=repo_root, ledger_path=ledger_path)
    emitted = []
    for receipt in pending:
        res = emit_conversion_receipt(
            receipt=receipt,
            channels=channels,
            dry_run=dry_run,
            ledger_path=ledger_path,
        )
        emitted.append(res)
    return emitted


def main():
    parser = argparse.ArgumentParser(description="MisakaNet intake conversion receipt engine")
    parser.add_argument("--scan", action="store_true", help="Scan and list pending conversion receipts")
    parser.add_argument("--emit", action="store_true", help="Scan and emit all pending receipts")
    parser.add_argument("--dry-run", action="store_true", help="Simulate receipt emission without posting")
    parser.add_argument("--channels", default="comment,webhook,ledger", help="Comma-separated channels to emit")
    parser.add_argument("--manual", action="store_true", help="Manually emit a receipt")
    parser.add_argument("--source", type=str, help="Source identifier")
    parser.add_argument("--issue", type=int, help="Intake issue number")
    parser.add_argument("--lesson", type=str, help="Lesson ID")
    parser.add_argument("--evidence", type=str, default="E2", help="Evidence level (e.g. E2)")
    parser.add_argument("--title", type=str, default="", help="Lesson title")
    parser.add_argument("--url", type=str, default=None, help="Lesson URL")
    parser.add_argument("--domain", type=str, default="general", help="Domain")

    args = parser.parse_args()
    active_channels = [c.strip() for c in args.channels.split(",") if c.strip()]

    if args.scan:
        pending = scan_promotions()
        print(f"Found {len(pending)} pending conversion receipt(s):")
        for p in pending:
            print(f"  - Issue #{p.get('intake_issue')} -> Lesson {p.get('lesson_id')} ({p.get('evidence_level')}) [Source: {p.get('source')}]")
    elif args.emit:
        results = run_pipeline(channels=active_channels, dry_run=args.dry_run)
        print(f"Processed {len(results)} conversion receipt(s).")
        for r in results:
            rcpt = r["receipt"]
            print(f"  Emitted {rcpt['receipt_id']}: comment={r.get('comment')} webhook={r.get('webhook')} ledger={r.get('ledger')}")
    elif args.manual:
        if not args.source or not args.issue or not args.lesson:
            print("Error: --source, --issue, and --lesson are required for --manual", file=sys.stderr)
            sys.exit(1)
        receipt = build_receipt(
            source=args.source,
            intake_issue=args.issue,
            lesson_id=args.lesson,
            lesson_title=args.title or args.lesson,
            evidence_level=args.evidence,
            lesson_url=args.url,
            domain=args.domain,
        )
        res = emit_conversion_receipt(receipt, channels=active_channels, dry_run=args.dry_run)
        print(f"Manually emitted receipt {receipt['receipt_id']}: comment={res.get('comment')} webhook={res.get('webhook')} ledger={res.get('ledger')}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
