#!/usr/bin/env python3
"""Unified feedback triage pipeline for MisakaNet.

Receives feedback from any source (search page, email, journey, danmaku, curl),
classifies it, routes to the appropriate output, and logs everything.

Usage:
    # From stdin (pipe JSON)
    echo '{"source":"search","query":"pip timeout","feedback":"helpful"}' | python3 scripts/triage_feedback.py

    # From file
    python3 scripts/triage_feedback.py --input data/search-feedback.jsonl

    # Single entry via argument
    python3 scripts/triage_feedback.py --json '{"source":"curl","message":"bug: search crashes","type":"bug"}'

    # Digest mode: show summary of logged feedback
    python3 scripts/triage_feedback.py --digest [--top 20]

Classification:
    lesson_candidate  — user solved something, wants to share
    rescue_card       — user is stuck, needs help
    bug_report        — something is broken in MisakaNet itself
    noise             — spam, empty, or unactionable

Routing:
    lesson_candidate → lessons/contrib/ draft file
    rescue_card      → lessons/user-rescue/ draft file
    bug_report       → data/bug-reports.jsonl (for GitHub Issue creation)
    noise            → discard (logged only)
"""
import argparse
import json
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_LOG = REPO_ROOT / "data" / "feedback-log.jsonl"
BUG_REPORTS = REPO_ROOT / "data" / "bug-reports.jsonl"
LESSONS_CONTRIB = REPO_ROOT / "lessons" / "contrib"
LESSONS_RESCUE = REPO_ROOT / "lessons" / "user-rescue"

# ── Classification keywords ──
RESCUE_SIGNALS = [
    "help", "stuck", "error", "fail", "broken", "crash", "timeout",
    "not working", "can't", "cannot", "how do i", "how to fix",
    "urgent", "blocked", "issue", "problem",
]
LESSON_SIGNALS = [
    "fixed", "solved", "solution", "workaround", "here's how",
    "i figured out", "the fix was", "resolved", "tip", "trick",
    "lesson", "learned", "discovered",
]
BUG_SIGNALS = [
    "bug", "regression", "broken in", "used to work", "misakanet",
    "search_knowledge", "worker", "endpoint", "api", "500",
    "internal error", "unexpected", "incorrect",
]


def classify(entry: dict) -> str:
    """Classify feedback into one of 4 categories."""
    # Explicit type field takes priority
    explicit = entry.get("type", "").lower()
    if explicit in ("lesson_candidate", "lesson"):
        return "lesson_candidate"
    if explicit in ("rescue_card", "rescue", "diagnostic"):
        return "rescue_card"
    if explicit in ("bug_report", "bug"):
        return "bug_report"
    if explicit in ("noise", "spam"):
        return "noise"

    # Keyword-based classification
    text = " ".join([
        str(entry.get("message", "")),
        str(entry.get("query", "")),
        str(entry.get("feedback", "")),
    ]).lower()

    if not text.strip():
        return "noise"

    bug_score = sum(1 for kw in BUG_SIGNALS if kw in text)
    rescue_score = sum(1 for kw in RESCUE_SIGNALS if kw in text)
    lesson_score = sum(1 for kw in LESSON_SIGNALS if kw in text)

    if bug_score > rescue_score and bug_score > lesson_score:
        return "bug_report"
    if lesson_score > rescue_score:
        return "lesson_candidate"
    if rescue_score > 0:
        return "rescue_card"

    # Feedback from search page with "helpful" = positive signal, not actionable
    if entry.get("feedback") in ("helpful", "y", "yes"):
        return "noise"  # positive feedback, log but don't route

    return "noise"


def route(entry: dict, category: str) -> str:
    """Route classified feedback to appropriate output. Returns action taken."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    entry_hash = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()[:8]

    if category == "lesson_candidate":
        LESSONS_CONTRIB.mkdir(parents=True, exist_ok=True)
        title = str(entry.get("message", entry.get("query", "untitled")))[:60]
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip()[:40]
        draft_path = LESSONS_CONTRIB / f"feedback-{ts}-{safe_title or entry_hash}.md"
        draft_path.write_text(
            f"---\n"
            f'{{"title": "{title}", "domain": "contrib", "tags": ["feedback-triage"], '
            f'"status": "draft", "source": "{entry.get("source", "unknown")}"}}\n'
            f"---\n\n"
            f"## Content\n\n{entry.get('message', entry.get('feedback', ''))}\n\n"
            f"## Metadata\n\n- Source: {entry.get('source', 'unknown')}\n"
            f"- Received: {datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )
        return f"draft:{draft_path.name}"

    elif category == "rescue_card":
        LESSONS_RESCUE.mkdir(parents=True, exist_ok=True)
        title = str(entry.get("message", entry.get("query", "rescue")))[:60]
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip()[:40]
        draft_path = LESSONS_RESCUE / f"rescue-{ts}-{safe_title or entry_hash}.md"
        draft_path.write_text(
            f"---\n"
            f'{{"title": "Rescue: {title}", "domain": "user-rescue", "tags": ["feedback-triage"], '
            f'"status": "draft", "source": "{entry.get("source", "unknown")}"}}\n'
            f"---\n\n"
            f"## Problem\n\n{entry.get('message', entry.get('query', ''))}\n\n"
            f"## Status\n\nAwaiting triage.\n",
            encoding="utf-8",
        )
        return f"draft:{draft_path.name}"

    elif category == "bug_report":
        BUG_REPORTS.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "id": entry_hash,
            "category": "bug_report",
            "message": str(entry.get("message", ""))[:500],
            "source": entry.get("source", "unknown"),
            "context": entry.get("context", {}),
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        with open(BUG_REPORTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return f"logged:{BUG_REPORTS.name}"

    else:  # noise
        return "discarded"


def log_entry(entry: dict, category: str, action: str) -> None:
    """Append to data/feedback-log.jsonl."""
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "source": entry.get("source", "unknown"),
        "category": category,
        "action": action,
        "query": str(entry.get("query", ""))[:200] or None,
        "message": str(entry.get("message", ""))[:200] or None,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def process_entry(entry: dict, verbose: bool = True) -> tuple[str, str]:
    """Process a single feedback entry. Returns (category, action)."""
    category = classify(entry)
    action = route(entry, category)
    log_entry(entry, category, action)
    if verbose:
        icon = {"lesson_candidate": "\U0001f4d6", "rescue_card": "\U0001f6a8",
                "bug_report": "\U0001f41b", "noise": "\U0001f5d1\ufe0f"}.get(category, "?")
        print(f"  {icon} [{category}] {action}")
    return category, action


def digest(top: int = 20) -> None:
    """Show summary of logged feedback."""
    if not FEEDBACK_LOG.exists():
        print("No feedback logged yet.")
        return

    from collections import Counter
    entries = []
    with open(FEEDBACK_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not entries:
        print("No feedback logged yet.")
        return

    by_cat = Counter(e.get("category", "?") for e in entries)
    by_src = Counter(e.get("source", "?") for e in entries)

    print(f"\n{'='*50}")
    print(f"  Feedback Triage Digest — {len(entries)} entries")
    print(f"{'='*50}")
    print(f"\n  By category:")
    for cat, count in by_cat.most_common():
        print(f"    {cat:<20} {count}")
    print(f"\n  By source:")
    for src, count in by_src.most_common():
        print(f"    {src:<20} {count}")
    print(f"\n  Recent ({min(top, len(entries))}):")
    for e in entries[-top:]:
        cat = e.get("category", "?")[:14]
        src = e.get("source", "?")[:8]
        msg = (e.get("message") or e.get("query") or "")[:50]
        print(f"    [{cat:<14}] {src:<8} {msg}")
    print()


def main():
    parser = argparse.ArgumentParser(description="MisakaNet feedback triage pipeline")
    parser.add_argument("--input", "-i", help="Read JSONL feedback from file")
    parser.add_argument("--json", "-j", help="Process a single JSON entry")
    parser.add_argument("--digest", action="store_true", help="Show feedback digest")
    parser.add_argument("--top", type=int, default=20, help="Entries to show in digest")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress per-entry output")
    args = parser.parse_args()

    if args.digest:
        digest(args.top)
        return

    entries = []

    if args.json:
        try:
            entries = [json.loads(args.json)]
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    else:
        # Read from stdin
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(1)
        for line in sys.stdin:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not entries:
        print("No feedback entries to process.")
        return

    verbose = not args.quiet
    if verbose:
        print(f"\n  Processing {len(entries)} feedback entr{'y' if len(entries) == 1 else 'ies'}...\n")

    stats = {"lesson_candidate": 0, "rescue_card": 0, "bug_report": 0, "noise": 0}
    for entry in entries:
        category, _ = process_entry(entry, verbose=verbose)
        stats[category] = stats.get(category, 0) + 1

    if verbose:
        print(f"\n  Done: {stats['lesson_candidate']} lessons, "
              f"{stats['rescue_card']} rescues, "
              f"{stats['bug_report']} bugs, "
              f"{stats['noise']} noise")
        print(f"  Log: {FEEDBACK_LOG}\n")


if __name__ == "__main__":
    main()
