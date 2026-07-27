#!/usr/bin/env python3
"""
Auto-triage feedback engine for MisakaNet.
Classifies incoming feedback into:
  - lesson-candidate: Problem + fix described -> Draft lesson in lessons/contrib/
  - rescue-card: Problem described, no fix -> Draft rescue card in lessons/user-rescue/
  - bug-report: Bug in MisakaNet -> Issue candidate (logged to JSONL for maintainer)
  - noise: Spam/vague/no signal -> Discard (logged but not routed)

Unified intake pipeline for feedback from any source:
  - Search page feedback button
  - Email (bot@misakanet.org)
  - Journey reports
  - Danmaku (future)

All intake is logged to data/feedback-log.jsonl for audit and digest generation.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# ── Paths ──────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_LOG = REPO_ROOT / "data" / "feedback-log.jsonl"


def classify_feedback(text: str) -> Tuple[str, float, Dict[str, Any]]:
    """Classify a feedback text into one of four categories."""
    clean_text = text.strip()
    words = clean_text.split()
    
    if len(words) < 5 or not clean_text:
        return "noise", 0.95, {"reason": "Feedback too short or empty"}
    
    text_lower = clean_text.lower()

    # Keywords signaling a fix or solution
    fix_indicators = [
        "fixed by", "how to fix", "solution:", "resolved by",
        "fix:", "workaround:", "resolution:", "here is the fix"
    ]
    has_fix = any(ind in text_lower for ind in fix_indicators) or "```" in text

    # Keywords signaling an error or symptom
    problem_indicators = [
        "error:", "exception:", "failed with", "traceback",
        "cannot connect", "unable to", "issue:", "bug:", "problem:"
    ]
    has_problem = any(ind in text_lower for ind in problem_indicators)

    # Keywords signaling MisakaNet internal bugs
    misaka_bug_indicators = [
        "misakanet", "wrangler.jsonc", "worker 500", "bench_orchestrator"
    ]
    is_misaka_bug = any(ind in text_lower for ind in misaka_bug_indicators)

    if is_misaka_bug and not has_fix:
        return "bug-report", 0.90, {"category": "bug-report"}

    if has_fix and (has_problem or len(words) >= 15):
        return "lesson-candidate", 0.88, {"category": "lesson-candidate"}

    if has_problem and not has_fix:
        return "rescue-card", 0.85, {"category": "rescue-card"}

    return "noise", 0.70, {"reason": "No actionable problem or fix identified"}


def _ensure_log_dir():
    """Create data/ directory if it doesn't exist."""
    FEEDBACK_LOG.parent.mkdir(parents=True, exist_ok=True)


def log_intake(entry: Dict[str, Any]) -> None:
    """Append a feedback intake record to data/feedback-log.jsonl."""
    _ensure_log_dir()
    with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def save_triage_draft(category: str, text: str, output_dir: Path) -> Path:
    """Save a draft file for lesson-candidate or rescue-card categories."""
    timestamp = int(time.time())
    slug = re.sub(r'[^a-z0-9]+', '-', text[:30].lower()).strip('-') or "feedback"
    
    if category == "lesson-candidate":
        target_dir = output_dir / "lessons" / "contrib"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"draft-{timestamp}-{slug}.md"
        content = f"""---
title: "Draft Lesson: {text[:50]}"
type: lesson-candidate
created_at: {timestamp}
status: draft
---

# Problem & Solution Draft

{text}
"""
    elif category == "rescue-card":
        target_dir = output_dir / "lessons" / "user-rescue"
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"rescue-{timestamp}-{slug}.md"
        content = f"""---
title: "Rescue Card: {text[:50]}"
type: rescue-card
created_at: {timestamp}
status: open
---

# Unresolved User Issue

{text}
"""
    else:
        file_path = output_dir / f"{category}-{timestamp}.json"
        content = json.dumps({"category": category, "text": text}, indent=2)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path


def route_feedback(
    category: str,
    text: str,
    source: str = "unknown",
    metadata: Optional[Dict[str, Any]] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Route classified feedback to the appropriate output.

    Args:
        category: One of lesson-candidate, rescue-card, bug-report, noise
        text: The feedback text
        source: Source channel (search-page, email, journey-report, danmaku)
        metadata: Optional extra metadata (lesson_id, query, user_agent, etc.)
        output_dir: Where to save draft files (default: repo root)

    Returns:
        Dict with routing result and log entry.
    """
    if output_dir is None:
        output_dir = REPO_ROOT

    timestamp = int(time.time())
    result = {
        "category": category,
        "source": source,
        "routed": False,
        "action": "none",
        "draft_path": None,
        "timestamp": timestamp,
    }

    if category == "lesson-candidate":
        draft_path = save_triage_draft(category, text, output_dir)
        result["routed"] = True
        result["action"] = "draft-lesson"
        result["draft_path"] = str(draft_path.relative_to(output_dir))

    elif category == "rescue-card":
        draft_path = save_triage_draft(category, text, output_dir)
        result["routed"] = True
        result["action"] = "draft-rescue"
        result["draft_path"] = str(draft_path.relative_to(output_dir))

    elif category == "bug-report":
        # Logged to JSONL for maintainer review (GitHub Issue creation is manual)
        result["routed"] = True
        result["action"] = "logged-for-review"

    elif category == "noise":
        result["action"] = "discarded"

    # Build log entry
    log_entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp)),
        "source": source,
        "category": category,
        "text": text[:500],  # Truncate for log
        "action": result["action"],
        "draft_path": result.get("draft_path"),
        "metadata": metadata or {},
    }
    log_intake(log_entry)

    return result


def process_feedback(
    feedback: Dict[str, Any],
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Process a feedback payload from any source.

    Expected payload format:
    {
        "text": "Error description or feedback text",
        "source": "search-page",  # or "email", "journey-report", "danmaku"
        "metadata": {  # optional
            "lesson_id": "...",
            "query": "...",
            "feedback_type": "helpful" | "too_basic" | "irrelevant"
        }
    }

    Returns routing result dict.
    """
    text = feedback.get("text", "").strip()
    source = feedback.get("source", "unknown")
    metadata = feedback.get("metadata", {})

    if not text:
        # Attempt to construct text from feedback type + lesson info
        fb_type = metadata.get("feedback_type", "")
        lesson_id = metadata.get("lesson_id", "")
        query = metadata.get("query", "")
        if fb_type and lesson_id:
            text = f"Search feedback: user found lesson {lesson_id} {fb_type} for query '{query}'"

    if not text:
        category, confidence, details = "noise", 1.0, {"reason": "Empty feedback"}
    else:
        category, confidence, details = classify_feedback(text)

    result = route_feedback(category, text, source=source, metadata=metadata, output_dir=output_dir)
    result["confidence"] = confidence
    result["details"] = details
    return result


def generate_digest(days: int = 7) -> str:
    """Generate a weekly digest of feedback intake from the JSONL log."""
    if not FEEDBACK_LOG.exists():
        return "No feedback log found."

    cutoff = time.time() - (days * 86400)
    entries = []
    with open(FEEDBACK_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Parse timestamp
                ts_str = entry.get("ts", "")
                try:
                    ts = time.mktime(time.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ"))
                except ValueError:
                    ts = 0
                if ts >= cutoff:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue

    if not entries:
        return f"No feedback in the last {days} days."

    # Count by category and source
    by_category = {}
    by_source = {}
    for e in entries:
        cat = e.get("category", "unknown")
        src = e.get("source", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        by_source[src] = by_source.get(src, 0) + 1

    lines = [
        f"## Feedback Digest (last {days} days)",
        f"**Total intake:** {len(entries)} items",
        "",
        "### By Category",
    ]
    for cat, count in sorted(by_category.items()):
        lines.append(f"- {cat}: {count}")

    lines.append("")
    lines.append("### By Source")
    for src, count in sorted(by_source.items()):
        lines.append(f"- {src}: {count}")

    lines.append("")
    lines.append("### Recent Bug Reports")
    bug_reports = [e for e in entries if e.get("category") == "bug-report"]
    if bug_reports:
        for br in bug_reports[-5:]:
            lines.append(f"- [{br.get('ts', '?')}] {br.get('text', '')[:100]}")
    else:
        lines.append("None")

    lines.append("")
    lines.append("### Action Items")
    lesson_candidates = [e for e in entries if e.get("category") == "lesson-candidate"]
    rescue_cards = [e for e in entries if e.get("category") == "rescue-card"]
    if lesson_candidates:
        lines.append(f"- Review {len(lesson_candidates)} lesson candidates in `lessons/contrib/`")
    if rescue_cards:
        lines.append(f"- Review {len(rescue_cards)} rescue cards in `lessons/user-rescue/`")
    if not lesson_candidates and not rescue_cards:
        lines.append("- No action items")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="MisakaNet Feedback Triage Engine")
    sub = parser.add_subparsers(dest="command")

    # classify subcommand
    classify_parser = sub.add_parser("classify", help="Classify a feedback text")
    classify_parser.add_argument("text", nargs="?", help="Feedback text (or stdin)")

    # process subcommand
    process_parser = sub.add_parser("process", help="Process a JSON feedback payload")
    process_parser.add_argument("json_file", nargs="?", help="JSON file (or stdin)")

    # digest subcommand
    digest_parser = sub.add_parser("digest", help="Generate feedback digest")
    digest_parser.add_argument("--days", type=int, default=7, help="Days to include (default: 7)")

    args = parser.parse_args()

    if args.command == "classify":
        if args.text:
            feedback_input = args.text
        else:
            feedback_input = sys.stdin.read()
        category, confidence, details = classify_feedback(feedback_input)
        print(f"Classification: {category} (Confidence: {confidence:.2f})")
        print(f"Details: {details}")

    elif args.command == "process":
        if args.json_file:
            with open(args.json_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = json.loads(sys.stdin.read())
        result = process_feedback(payload)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "digest":
        print(generate_digest(days=args.days))

    else:
        # Default: classify from stdin or argv
        if len(sys.argv) > 1:
            feedback_input = sys.argv[1]
            category, confidence, details = classify_feedback(feedback_input)
            print(f"Classification: {category} (Confidence: {confidence:.2f})")
            print(f"Details: {details}")
        else:
            feedback_input = sys.stdin.read()
            if feedback_input.strip():
                category, confidence, details = classify_feedback(feedback_input)
                print(f"Classification: {category} (Confidence: {confidence:.2f})")
                print(f"Details: {details}")
            else:
                parser.print_help()


if __name__ == "__main__":
    main()
