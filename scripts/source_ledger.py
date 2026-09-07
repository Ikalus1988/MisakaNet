#!/usr/bin/env python3
"""Intake source ledger.

Tracks per-source submissions, deduplications, lesson promotions,
and conversion receipts. Decoupled from intake deduplication (#1526)
to feed conversion receipts (#1528).

Usage:
    python3 scripts/source_ledger.py summary
    python3 scripts/source_ledger.py show <source>
    python3 scripts/source_ledger.py record-submission --source <source> [--issue <num>]
    python3 scripts/source_ledger.py record-dedup --source <source> [--count <n>]
    python3 scripts/source_ledger.py record-promotion --source <source> --lesson <id> --issue <num> --evidence <level> [--title <title>]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO_ROOT / "data" / "source_ledger.json"
LEDGER_FILE = LEDGER_PATH


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def default_ledger() -> dict:
    """Return an empty source ledger structure."""
    return {
        "_schema": "1.0",
        "_description": "MisakaNet intake source ledger — tracks submissions, deduplications, promotions, and receipts per source.",
        "_last_updated": _now_iso(),
        "sources": {},
    }


def load_ledger(path: Path | str = None) -> dict:
    """Load source ledger from JSON file or return default structure."""
    target_path = Path(path) if path else LEDGER_PATH
    if not target_path.exists():
        return default_ledger()
    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "sources" not in data:
            return default_ledger()
        return data
    except Exception:
        return default_ledger()


def save_ledger(ledger: dict, path: Path | str = None) -> None:
    """Save source ledger atomically to disk."""
    target_path = Path(path) if path else LEDGER_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    ledger["_last_updated"] = _now_iso()
    temp_path = target_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(target_path)


def _init_source_entry(source: str) -> dict:
    """Create default record for a new source."""
    return {
        "source": source,
        "submitted": 0,
        "deduped": 0,
        "promoted": 0,
        "conversion_rate": 0.0,
        "intake_issues": [],
        "lessons": [],
        "receipts": [],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def _update_conversion_rate(entry: dict) -> None:
    """Calculate conversion rate: promoted / submitted."""
    submitted = entry.get("submitted", 0)
    promoted = entry.get("promoted", 0)
    if submitted > 0:
        entry["conversion_rate"] = round(promoted / submitted, 3)
    elif promoted > 0:
        entry["conversion_rate"] = 1.0
    else:
        entry["conversion_rate"] = 0.0


def record_submission(source: str, issue_number: int | str = None, path: Path | str = None) -> dict:
    """Record an intake submission from a source."""
    clean_source = str(source).strip() if source else "unknown"
    ledger = load_ledger(path)
    entry = ledger["sources"].setdefault(clean_source, _init_source_entry(clean_source))
    entry["submitted"] = entry.get("submitted", 0) + 1
    if issue_number is not None:
        try:
            num = int(issue_number)
            if num not in entry["intake_issues"]:
                entry["intake_issues"].append(num)
        except (ValueError, TypeError):
            pass
    entry["updated_at"] = _now_iso()
    _update_conversion_rate(entry)
    save_ledger(ledger, path)
    return entry


def record_dedup(source: str, count: int = 1, path: Path | str = None) -> dict:
    """Record that an intake was intercepted by the deduplication gate (#1526)."""
    clean_source = str(source).strip() if source else "unknown"
    ledger = load_ledger(path)
    entry = ledger["sources"].setdefault(clean_source, _init_source_entry(clean_source))
    entry["deduped"] = entry.get("deduped", 0) + count
    entry["updated_at"] = _now_iso()
    _update_conversion_rate(entry)
    save_ledger(ledger, path)
    return entry


def record_promotion(
    source: str,
    lesson_id: str,
    intake_issue: int | str,
    evidence_level: str,
    title: str = "",
    url: str = None,
    path: Path | str = None,
) -> dict:
    """Record that an intake has been promoted into an active lesson."""
    clean_source = str(source).strip() if source else "unknown"
    ledger = load_ledger(path)
    entry = ledger["sources"].setdefault(clean_source, _init_source_entry(clean_source))

    intake_num = None
    if intake_issue is not None:
        try:
            intake_num = int(intake_issue)
            if intake_num not in entry["intake_issues"]:
                entry["intake_issues"].append(intake_num)
        except (ValueError, TypeError):
            pass

    existing_lesson = next((l for l in entry.get("lessons", []) if l.get("lesson_id") == lesson_id), None)
    now = _now_iso()

    if existing_lesson:
        existing_lesson["evidence_level"] = evidence_level
        if title:
            existing_lesson["title"] = title
        if url:
            existing_lesson["url"] = url
        if intake_num is not None:
            existing_lesson["intake_issue"] = intake_num
        existing_lesson["updated_at"] = now
    else:
        entry["lessons"].append({
            "lesson_id": lesson_id,
            "title": title or lesson_id,
            "url": url or f"https://misakanet.org/lessons/{lesson_id}/",
            "intake_issue": intake_num,
            "evidence_level": evidence_level,
            "promoted_at": now,
        })
        entry["promoted"] = entry.get("promoted", 0) + 1

    entry["updated_at"] = now
    _update_conversion_rate(entry)
    save_ledger(ledger, path)
    return entry


def record_receipt(
    source: str,
    receipt_id: str,
    channel: str,
    intake_issue: int | str,
    lesson_id: str,
    path: Path | str = None,
) -> dict:
    """Record an emitted receipt for an intake and lesson."""
    clean_source = str(source).strip() if source else "unknown"
    ledger = load_ledger(path)
    entry = ledger["sources"].setdefault(clean_source, _init_source_entry(clean_source))

    intake_num = None
    if intake_issue is not None:
        try:
            intake_num = int(intake_issue)
        except (ValueError, TypeError):
            pass

    existing = next((r for r in entry.get("receipts", []) if r.get("receipt_id") == receipt_id), None)
    if not existing:
        entry["receipts"].append({
            "receipt_id": receipt_id,
            "intake_issue": intake_num,
            "lesson_id": lesson_id,
            "channel": channel,
            "emitted_at": _now_iso(),
        })
        entry["updated_at"] = _now_iso()
        save_ledger(ledger, path)
    return entry


def is_receipt_emitted(
    source_or_issue: str | int = None,
    intake_issue_or_lesson: int | str = None,
    lesson_id: str = None,
    path: Path | str = None,
) -> bool:
    """Check if a receipt was already emitted for this intake and lesson pair."""
    if lesson_id is None and intake_issue_or_lesson is not None:
        intake_issue = source_or_issue
        target_lesson_id = str(intake_issue_or_lesson)
        source = None
    else:
        source = str(source_or_issue) if source_or_issue else None
        intake_issue = intake_issue_or_lesson
        target_lesson_id = str(lesson_id) if lesson_id else None

    ledger = load_ledger(path)
    clean_source = str(source).strip() if source else ""
    intake_num = None
    if intake_issue is not None:
        try:
            intake_num = int(intake_issue)
        except (ValueError, TypeError):
            pass

    def _matches(receipt: dict) -> bool:
        if target_lesson_id and receipt.get("lesson_id") != target_lesson_id:
            return False
        if intake_num is not None and receipt.get("intake_issue") == intake_num:
            return True
        return False

    if clean_source and clean_source in ledger.get("sources", {}):
        return any(_matches(r) for r in ledger["sources"][clean_source].get("receipts", []))

    for s_data in ledger.get("sources", {}).values():
        if any(_matches(r) for r in s_data.get("receipts", [])):
            return True
    return False


def sync_promotions_from_lessons(lessons_path: Path | str = None, ledger_path: Path | str = None) -> dict:
    """Scan lessons.json and sync all promoted lessons to the ledger."""
    l_path = Path(lessons_path) if lessons_path else (REPO_ROOT / "data" / "lessons.json")
    if not l_path.exists():
        return {"synced": 0}
    lessons = json.loads(l_path.read_text(encoding="utf-8"))
    synced = 0
    for lesson in lessons:
        source = lesson.get("source")
        intake_issue = lesson.get("intake_issue")
        l_id = lesson.get("id")
        if source and l_id:
            record_promotion(
                source=source,
                lesson_id=l_id,
                evidence_level=lesson.get("evidence_level", "E0"),
                intake_issue=intake_issue,
                title=lesson.get("title", l_id),
                path=ledger_path,
            )
            synced += 1
    return {"synced": synced}


def get_source_stats(source: str, path: Path | str = None) -> dict | None:
    """Get statistics and history for a given source."""
    ledger = load_ledger(path)
    return ledger.get("sources", {}).get(str(source).strip())


def get_summary(path: Path | str = None) -> dict:
    """Aggregate summary of all sources."""
    ledger = load_ledger(path)
    sources = ledger.get("sources", {})
    total_submitted = sum(s.get("submitted", 0) for s in sources.values())
    total_deduped = sum(s.get("deduped", 0) for s in sources.values())
    total_promoted = sum(s.get("promoted", 0) for s in sources.values())
    total_receipts = sum(len(s.get("receipts", [])) for s in sources.values())
    overall_conversion = round(total_promoted / total_submitted, 3) if total_submitted > 0 else 0.0

    return {
        "total_sources": len(sources),
        "total_submitted": total_submitted,
        "total_deduped": total_deduped,
        "total_promoted": total_promoted,
        "total_receipts": total_receipts,
        "overall_conversion_rate": overall_conversion,
        "sources": {
            k: {
                "submitted": v.get("submitted", 0),
                "deduped": v.get("deduped", 0),
                "promoted": v.get("promoted", 0),
                "conversion_rate": v.get("conversion_rate", 0.0),
                "receipts_count": len(v.get("receipts", [])),
            }
            for k, v in sources.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description="MisakaNet intake source ledger")
    sub = parser.add_subparsers(dest="command")

    p_sum = sub.add_parser("summary", help="Show aggregate summary of all sources")
    p_sum.add_argument("--path", type=Path, default=LEDGER_FILE)

    p_show = sub.add_parser("show", help="Show details for a specific source")
    p_show.add_argument("source", type=str)
    p_show.add_argument("--path", type=Path, default=LEDGER_FILE)

    p_sub = sub.add_parser("record-submission", help="Record an intake submission")
    p_sub.add_argument("--source", required=True, type=str)
    p_sub.add_argument("--issue", type=int, default=None)
    p_sub.add_argument("--path", type=Path, default=LEDGER_FILE)

    p_dedup = sub.add_parser("record-dedup", help="Record an intake deduplication")
    p_dedup.add_argument("--source", required=True, type=str)
    p_dedup.add_argument("--count", type=int, default=1)
    p_dedup.add_argument("--path", type=Path, default=LEDGER_FILE)

    p_prom = sub.add_parser("record-promotion", help="Record a lesson promotion")
    p_prom.add_argument("--source", required=True, type=str)
    p_prom.add_argument("--lesson", required=True, type=str)
    p_prom.add_argument("--issue", required=True, type=int)
    p_prom.add_argument("--evidence", required=True, type=str)
    p_prom.add_argument("--title", type=str, default="")
    p_prom.add_argument("--url", type=str, default=None)
    p_prom.add_argument("--path", type=Path, default=LEDGER_FILE)

    args = parser.parse_args()

    if args.command == "summary":
        summary = get_summary(args.path)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif args.command == "show":
        stats = get_source_stats(args.source, args.path)
        if stats:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print(f"Source not found: {args.source}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "record-submission":
        res = record_submission(args.source, args.issue, args.path)
        print(f"Recorded submission for {args.source}: submitted={res['submitted']}")
    elif args.command == "record-dedup":
        res = record_dedup(args.source, args.count, args.path)
        print(f"Recorded dedup for {args.source}: deduped={res['deduped']}")
    elif args.command == "record-promotion":
        res = record_promotion(args.source, args.lesson, args.issue, args.evidence, args.title, args.url, args.path)
        print(f"Recorded promotion for {args.source}: promoted={res['promoted']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
