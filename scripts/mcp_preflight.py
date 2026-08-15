#!/usr/bin/env python3
"""MisakaNet Preflight Risk Assessment & Lesson Retrieval Tool.

Proactively matches structured intent, commands, environment, and risk tags
against lesson trigger metadata before high-risk tasks execute.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DATA_LESSONS = REPO_ROOT / "data" / "lessons.json"

SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def load_lessons_with_triggers() -> List[Dict[str, Any]]:
    """Load indexed lessons that have triggers metadata from data/lessons.json."""
    if not DATA_LESSONS.exists():
        return []
    try:
        data = json.loads(DATA_LESSONS.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    if not text:
        return set()
    return set(re.findall(r"[a-zA-Z0-9_\-]+", text.lower()))


def evaluate_match(
    lesson: Dict[str, Any],
    intent: str,
    commands: Optional[List[str]] = None,
    environments: Optional[List[str]] = None,
    risks: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Score and match a lesson against intent, commands, environments, and risks."""
    triggers = lesson.get("triggers")
    if not isinstance(triggers, dict):
        return None

    matched_intents = []
    matched_commands = []
    matched_environments = []
    matched_risks = []

    intent_tokens = tokenize(intent)
    commands_tokens = set()
    for c in commands or []:
        commands_tokens.update(tokenize(c))

    env_tokens = set()
    for e in environments or []:
        env_tokens.update(tokenize(e))

    risk_tokens = set()
    for r in risks or []:
        risk_tokens.update(tokenize(r))

    # Match intents
    for it in triggers.get("intents", []):
        it_tokens = tokenize(it)
        if it_tokens and (it_tokens.issubset(intent_tokens) or any(t in intent_tokens for t in it_tokens)):
            matched_intents.append(it)

    # Match commands
    for cmd in triggers.get("commands", []):
        cmd_tokens = tokenize(cmd)
        if cmd_tokens and (cmd_tokens.issubset(commands_tokens) or any(t in commands_tokens for t in cmd_tokens) or cmd_tokens.issubset(intent_tokens)):
            matched_commands.append(cmd)

    # Match environments
    for env_tag in triggers.get("environments", []):
        e_tokens = tokenize(env_tag)
        if e_tokens and (e_tokens.issubset(env_tokens) or any(t in env_tokens for t in e_tokens)):
            matched_environments.append(env_tag)

    # Match risks
    for r_tag in triggers.get("risks", []):
        r_tokens = tokenize(r_tag)
        if r_tokens and (r_tokens.issubset(risk_tokens) or any(t in risk_tokens for t in r_tokens) or r_tokens.issubset(intent_tokens)):
            matched_risks.append(r_tag)

    score = (
        len(matched_intents) * 3
        + len(matched_commands) * 3
        + len(matched_environments) * 2
        + len(matched_risks) * 2
    )

    if score == 0:
        return None

    severity = triggers.get("severity", "medium").lower()
    severity_rank = SEVERITY_ORDER.get(severity, 2)

    return {
        "id": lesson.get("id"),
        "title": lesson.get("title"),
        "domain": lesson.get("domain"),
        "url": lesson.get("url"),
        "summary": lesson.get("summary"),
        "severity": severity,
        "severity_rank": severity_rank,
        "score": score,
        "matches": {
            "intents": matched_intents,
            "commands": matched_commands,
            "environments": matched_environments,
            "risks": matched_risks,
        },
    }


def preflight_check(
    intent: str,
    commands: Optional[List[str]] = None,
    environments: Optional[List[str]] = None,
    risks: Optional[List[str]] = None,
    lessons_data: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Execute structured preflight risk check and return relevant warnings/lessons."""
    lessons = lessons_data if lessons_data is not None else load_lessons_with_triggers()

    matched_results = []
    for l in lessons:
        res = evaluate_match(l, intent, commands, environments, risks)
        if res:
            matched_results.append(res)

    # Sort by (severity_rank DESC, score DESC)
    matched_results.sort(key=lambda x: (x["severity_rank"], x["score"]), reverse=True)

    highest_severity = "none"
    if matched_results:
        highest_severity = matched_results[0]["severity"]

    is_high_risk = highest_severity in ("critical", "high")

    return {
        "status": "warning" if matched_results else "clean",
        "intent": intent,
        "risk_level": highest_severity,
        "requires_confirmation": is_high_risk,
        "matched_count": len(matched_results),
        "recommendations": matched_results,
    }


def main():
    parser = argparse.ArgumentParser(description="MisakaNet MCP Preflight Tool")
    parser.add_argument("intent", help="Task or intent description")
    parser.add_argument("--command", "-c", action="append", help="Planned command or tool call")
    parser.add_argument("--env", "-e", action="append", help="Environment descriptor (e.g. wsl, gpu, cuda)")
    parser.add_argument("--risk", "-r", action="append", help="Anticipated risk descriptor")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    result = preflight_check(
        intent=args.intent,
        commands=args.command,
        environments=args.env,
        risks=args.risk,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== Preflight Check Result: {result['status'].upper()} ===")
        print(f"Risk Level: {result['risk_level'].upper()} (Requires Confirmation: {result['requires_confirmation']})")
        print(f"Matched Lessons: {result['matched_count']}")
        for item in result["recommendations"]:
            print(f"- [{item['severity'].upper()}] {item['title']} (score={item['score']}, url={item['url']})")
            if item['matches']['intents']:
                print(f"  Matched intents: {', '.join(item['matches']['intents'])}")
            if item['matches']['commands']:
                print(f"  Matched commands: {', '.join(item['matches']['commands'])}")
            if item['matches']['environments']:
                print(f"  Matched env: {', '.join(item['matches']['environments'])}")


if __name__ == "__main__":
    main()
