#!/usr/bin/env python3
"""Preflight MCP Tool — risk-aware lesson injection before high-risk tasks.

Matches agent intent against lesson triggers to provide proactive warnings.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_LESSONS = REPO_ROOT / "data" / "lessons.json"

# Risk profiles: keywords → risk level
RISK_PROFILES = {
    "rag_build": {
        "keywords": ["rag", "embedding", "vector", "chroma", "faiss", "index", "build_index"],
        "risk": "high",
        "guards": [
            "Start with 3-5 sample documents before full batch",
            "Set batch_size <= 8 to control memory usage",
            "Write checkpoint every N documents",
            "Monitor VRAM/RAM usage",
            "Test resume from checkpoint before scaling",
        ],
    },
    "wsl_gpu": {
        "keywords": ["wsl", "cuda", "gpu", "vram", "lm_studio"],
        "risk": "high",
        "guards": [
            "Check WSL memory limit in .wslconfig",
            "Monitor VRAM usage",
            "Avoid loading all models at once",
        ],
    },
    "bulk_import": {
        "keywords": ["unzip", "extract", "bulk", "batch_import"],
        "risk": "medium",
        "guards": [
            "Count files first",
            "Estimate total size",
            "Process in chunks",
            "Track progress",
        ],
    },
}


class LessonIndexUnreadable(Exception):
    """The lesson index this check depends on could not be read.

    This used to be `except Exception: pass` followed by `return []`, which is a result the caller
    cannot tell apart from "the index is fine and no lesson carries triggers" (#2940). Measured on
    the real corpus: an intent that matches `rag-build-strategy-batch` reports `risk: critical`
    with 1 matched lesson against the healthy index, and `risk: high` with 0 matched lessons
    against a truncated one — the `high` coming from the static keyword profile, so the only thing
    that had gone missing was the evidence.

    Raising is the honest option, for the same reason `UnreadableScanTarget` is raised in
    `check_worker_secrets.py`: a sentinel the caller has to remember to check is a sentinel some
    caller will not check. `preflight_check` is the one caller, and it converts this into an
    explicit status rather than letting it disappear.
    """

    def __init__(self, path: Path, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"{path} could not be used as a lesson index: {reason}")


def load_lessons_with_triggers() -> List[Dict[str, Any]]:
    """Load lessons that have triggers metadata, or refuse.

    Raises `LessonIndexUnreadable` rather than reporting no lessons. A missing file, an unreadable
    one, text that is not JSON, and JSON that is not a list are all evidence gaps, and none of
    them is "there is nothing here".
    """
    if not DATA_LESSONS.exists():
        raise LessonIndexUnreadable(DATA_LESSONS, "file does not exist")

    try:
        raw = DATA_LESSONS.read_text(encoding="utf-8")
    except OSError as exc:
        raise LessonIndexUnreadable(DATA_LESSONS, f"{exc.__class__.__name__}: {exc}") from exc

    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise LessonIndexUnreadable(DATA_LESSONS, f"not valid JSON ({exc})") from exc

    if not isinstance(data, list):
        raise LessonIndexUnreadable(
            DATA_LESSONS, f"expected a JSON list of lessons, got {type(data).__name__}"
        )

    return [lesson for lesson in data if isinstance(lesson, dict) and lesson.get("triggers")]


def tokenize(text: str) -> set:
    """Tokenize text into lowercase alphanumeric tokens."""
    if not text:
        return set()
    return set(re.findall(r"[a-zA-Z0-9_\-]+", text.lower()))


def match_triggers(
    intent: str,
    context: str = "",
    triggers: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Match intent against lesson triggers."""
    if not triggers:
        return {"score": 0, "matched": []}

    intent_tokens = tokenize(intent)
    context_tokens = tokenize(context)
    all_tokens = intent_tokens | context_tokens

    matched = []
    for trigger_type in ["intents", "commands", "environments", "risks"]:
        for keyword in triggers.get(trigger_type, []):
            kw_tokens = tokenize(keyword)
            if kw_tokens and (kw_tokens & all_tokens):
                matched.append(f"{trigger_type}:{keyword}")

    return {"score": len(matched), "matched": matched}


def preflight_check(
    intent: str,
    context: str = "",
) -> Dict[str, Any]:
    """Main preflight entry point."""
    # 1. Check risk profiles
    matched_profiles = []
    for profile_name, profile in RISK_PROFILES.items():
        intent_lower = intent.lower()
        if any(kw in intent_lower for kw in profile["keywords"]):
            matched_profiles.append({
                "name": profile_name,
                "risk": profile["risk"],
                "guards": profile["guards"],
            })

    # 2. Check lesson triggers
    index_status = "ok"
    index_error = None
    try:
        lessons = load_lessons_with_triggers()
    except LessonIndexUnreadable as exc:
        # The keyword profiles above still stand — they are a literal table in this file. What is
        # missing is the lesson evidence, and a caller reading `matched_lessons: []` cannot tell
        # that from a lesson that simply did not match. So it is stated, and the recommendation
        # stops claiming the operation is safe.
        index_status = "unreadable"
        index_error = str(exc)
        lessons = []

    matched_lessons = []
    for lesson in lessons:
        triggers = lesson.get("triggers", {})
        match_result = match_triggers(intent, context, triggers)
        if match_result["score"] > 0:
            matched_lessons.append({
                "id": lesson.get("id"),
                "title": lesson.get("title"),
                "severity": triggers.get("severity", "medium"),
                "score": match_result["score"],
                "matched": match_result["matched"],
            })

    # 3. Determine overall risk
    all_risks = [p["risk"] for p in matched_profiles] + [l["severity"] for l in matched_lessons]
    if "critical" in all_risks:
        risk = "critical"
    elif "high" in all_risks:
        risk = "high"
    elif "medium" in all_risks:
        risk = "medium"
    else:
        risk = "low"

    # 4. Combine guards
    all_guards = []
    for p in matched_profiles:
        all_guards.extend(p["guards"])

    if index_status != "ok":
        recommendation = (
            f"Lesson index unreadable ({index_error}); the risk above reflects keyword profiles "
            "only, and no lesson evidence was checked. Treat as unverified."
        )
    elif risk in ("high", "critical"):
        recommendation = "Run small-scale probe first, then scale"
    else:
        recommendation = "Safe to proceed"

    return {
        "risk": risk,
        "matched_profiles": matched_profiles,
        "matched_lessons": matched_lessons,
        "guards": list(set(all_guards)),
        "recommendation": recommendation,
        # `ok` or `unreadable`. Added because `matched_lessons: []` was documented as the normal
        # signal for "the profile matched but no lesson was close enough" — which made a corrupted
        # index indistinguishable from a clean one to exactly the clients most likely to rely on it.
        "index_status": index_status,
        "index_error": index_error,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Preflight risk check")
    parser.add_argument("intent", help="Task intent description")
    parser.add_argument("--context", default="", help="Environment context")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    result = preflight_check(args.intent, args.context)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        risk_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        print(f"Risk: {risk_icons.get(result['risk'], '⚪')} {result['risk']}")
        print(f"Recommendation: {result['recommendation']}")
        if result["matched_lessons"]:
            print(f"Matched lessons: {len(result['matched_lessons'])}")
            for l in result["matched_lessons"]:
                print(f"  - {l['title']} (severity: {l['severity']})")
        if result["guards"]:
            print("Guards:")
            for g in result["guards"][:3]:
                print(f"  - {g}")

    # The printout above already says the evidence was missing; the exit code is what stops a
    # pipeline from reading the same run as a pass. This script used to always exit 0.
    if result["index_status"] != "ok":
        print(f"\nLesson index unusable: {result['index_error']}", file=sys.stderr)
        sys.exit(1)
