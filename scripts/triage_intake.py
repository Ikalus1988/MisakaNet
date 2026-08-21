#!/usr/bin/env python3
"""Route intake submissions into: lesson / rescue / bug / noise.

Run: python scripts/triage_intake.py [--dry-run]
"""

import json
import os
import re
import sys
from pathlib import Path

LESSONS_DIR = Path(__file__).resolve().parent.parent / "lessons"


def extract_keywords(text: str) -> list[str]:
    """Extract lowercase keywords from text."""
    return re.findall(r"[a-z][\w-]{2,}", text.lower())


def classify(text: str) -> tuple[str, str, str]:
    """Classify intake text into a category with label and confidence.

    Returns (category, label, reason).
    """
    text_lower = text.lower()
    keywords = set(extract_keywords(text))

    # ── Rescue patterns (operational, urgent) ──────────────────
    rescue_patterns = [
        (r"prod(uction)?", "production"),
        (r"outage|down|offline", "outage"),
        (r"urgent|critical|emergency|p[01]", "urgent"),
        (r"hotfix|rollback|revert", "hotfix"),
        (r"incident|postmortem", "incident"),
    ]
    rescue_score = 0
    rescue_reasons = []
    for pat, label in rescue_patterns:
        if re.search(pat, text_lower):
            rescue_score += 2
            rescue_reasons.append(label)

    # ── Bug patterns ──────────────────────────────────────────
    bug_patterns = [
        (r"bug|defect|broken|crash|fail", "crash"),
        (r"error\s+message|stack\s*trace|traceback", "traceback"),
        (r"regression|broke\s+after|used\s+to\s+work", "regression"),
        (r"fix|patch|resolve", "fix-request"),
    ]
    bug_score = 0
    bug_reasons = []
    for pat, label in bug_patterns:
        if re.search(pat, text_lower):
            bug_score += 2
            bug_reasons.append(label)

    # ── Lesson patterns (educational, reusable) ───────────────
    lesson_patterns = [
        (r"lesson|learn(?:ing|ed)?|takeaway", "lesson-keyword"),
        (r"pattern|anti-pattern|best\s+practice", "pattern"),
        (r"mistake|wrong\s+approach|pitfall", "pitfall"),
        (r"tip|trick|hint|shortcut", "tip"),
        (r"how\s+to|tutorial|guide", "guide"),
        (r"debug(?:ging)?|troubleshoot(?:ing)?", "debug"),
    ]
    lesson_score = 0
    lesson_reasons = []
    for pat, label in lesson_patterns:
        if re.search(pat, text_lower):
            lesson_score += 2
            lesson_reasons.append(label)

    # ── Noise patterns ────────────────────────────────────────
    noise_patterns = [
        (r"^.{0,30}$", "too-short"),
        (r"(?:test|hello|lorem|asdf|test123)", "test-input"),
        (r"(?:spam|junk|garbage)", "spam"),
    ]
    noise_score = 0
    noise_reasons = []
    for pat, label in noise_patterns:
        if re.search(pat, text_lower):
            noise_score += 3
            noise_reasons.append(label)

    # ── Decision ──────────────────────────────────────────────
    scores = {
        "lesson": lesson_score,
        "rescue": rescue_score,
        "bug": bug_score,
        "noise": noise_score,
    }
    best = max(scores, key=scores.get)

    # Tie-break: bug > rescue > lesson > noise
    if scores[best] == 0:
        return ("noise", "No strong signal", "No keyword patterns matched")

    reasons = {
        "lesson": lesson_reasons,
        "rescue": rescue_reasons,
        "bug": bug_reasons,
        "noise": noise_reasons,
    }

    return (best, f"{best} ({', '.join(reasons[best][:3])})", f"Score: {scores[best]}")


def main():
    dry_run = "--dry-run" in sys.argv

    if len(sys.argv) < 2:
        print("Usage: python scripts/triage_intake.py <file|->")
        print("  - reads from stdin")
        print("  file reads from file")
        print("  --dry-run shows classification without acting")
        sys.exit(1)

    source = sys.argv[-1] if sys.argv[-1] != "--dry-run" else "-"
    if source == "-":
        text = sys.stdin.read().strip()
    else:
        text = Path(source).read_text(encoding="utf-8").strip()

    if not text:
        print("Empty input")
        sys.exit(1)

    category, label, reason = classify(text)

    result = {
        "category": category,
        "label": label,
        "reason": reason,
        "input_length": len(text),
    }

    if dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if category == "lesson":
            print("\n→ Route to: lessons/ directory")
        elif category == "rescue":
            print("\n→ Route to: rescue/issues/ (urgent)")
        elif category == "bug":
            print("\n→ Route to: rescue/issues/ (bug)")
        else:
            print("\n→ Route to: noise (discard or flag)")


if __name__ == "__main__":
    main()
