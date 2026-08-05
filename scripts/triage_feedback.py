#!/usr/bin/env python3
"""
Auto-triage feedback engine for MisakaNet.
Classifies incoming feedback into:
  - lesson-candidate: Problem + fix described -> Draft lesson in lessons/contrib/
  - rescue-card: Problem described, no fix -> Draft rescue card in lessons/user-rescue/
  - bug-report: Bug in MisakaNet -> Issue candidate
  - noise: Spam/vague/no signal -> Discard
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple


def classify_feedback(text: str) -> Tuple[str, float, Dict[str, Any]]:
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
        "error:", "error ", "exception:", "failed with", "traceback",
        "cannot connect", "unable to", "issue:", "bug:", "problem:",
        " 500 ", "500 error",
    ]
    has_problem = any(ind in text_lower for ind in problem_indicators)

    # Keywords signaling MisakaNet internal bugs
    misaka_bug_indicators = [
        "misakanet", "wrangler.jsonc", "worker 500", "bench_orchestrator"
    ]
    is_misaka_bug = any(ind in text_lower for ind in misaka_bug_indicators)

    # Product-area signals alone are enough: users rarely write "Error:" prefixes
    if is_misaka_bug and not has_fix:
        return "bug-report", 0.90, {"category": "bug-report"}

    if has_fix and (has_problem or len(words) >= 15):
        return "lesson-candidate", 0.88, {"category": "lesson-candidate"}

    if has_problem and not has_fix:
        return "rescue-card", 0.85, {"category": "rescue-card"}

    return "noise", 0.70, {"reason": "No actionable problem or fix identified"}


def save_triage_draft(category: str, text: str, output_dir: Path) -> Path:
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


def main():
    if len(sys.argv) > 1:
        feedback_input = sys.argv[1]
    else:
        feedback_input = sys.stdin.read()

    category, confidence, details = classify_feedback(feedback_input)
    print(f"Classification: {category} (Confidence: {confidence:.2f})")
    print(f"Details: {details}")


if __name__ == "__main__":
    main()
