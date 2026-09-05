#!/usr/bin/env python3
"""Intake kind inference — question vs failure routing for MCP intake entries.

Mirror of ``workers/lib/utils.js`` ``inferIntakeKind`` (same tables, same
rules). Used by :mod:`scripts.mcp_http_server` so that how-to / knowledge-gap
submissions are routed as ``kind="question"`` instead of being treated as
malformed failure lessons (see #1396: a PT-BR how-to arrived as
``kind=missing_lesson``, was scored 16.9/100 by the lesson auto-review and
auto-rejected to badcase — a dead end for question-shaped content).

Conservative on purpose: only clear question phrasing with NO failure evidence
(error/fix/verification fields or failure keywords) flips the kind; real
failure intakes are never touched.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

INTAKE_KINDS = ("missing_lesson", "stale_lesson", "new_lesson_candidate", "question")

# Single source of truth: data/intake-kind-hints.json
_HINTS_PATH = Path(__file__).resolve().parent.parent / "data" / "intake-kind-hints.json"
_HINTS = json.loads(_HINTS_PATH.read_text(encoding="utf-8"))
QUESTION_HINTS: list[str] = _HINTS["question_hints"]
FAILURE_HINTS: list[str] = _HINTS["failure_hints"]

_QUESTION_RE = [re.compile(p, re.IGNORECASE) for p in QUESTION_HINTS]
_FAILURE_RE = [re.compile(p, re.IGNORECASE) for p in FAILURE_HINTS]


def looks_like_question(text: str) -> bool:
    """True if the text carries a question/help phrasing hint."""
    t = str(text or "")
    return any(r.search(t) for r in _QUESTION_RE)


def has_failure_evidence(text: str) -> bool:
    """True if the text carries failure/error keywords."""
    t = str(text or "")
    return any(r.search(t) for r in _FAILURE_RE)


def infer_intake_kind(
    kind: str = "",
    problem: str = "",
    error: str = "",
    what_tried: str = "",
    fix: str = "",
    verification: str = "",
) -> tuple[str, bool]:
    """Resolve the intake kind for a submission.

    - An explicit, valid kind (stale_lesson / new_lesson_candidate / question /
      missing_lesson) is honored as-is, EXCEPT ``kind="missing_lesson"``:
      callers are still guided toward it by older copy, so a clear question
      with zero failure evidence is re-routed to ``"question"``.
    - An absent kind defaults to ``"missing_lesson"``, upgraded to
      ``"question"`` under the same rule.

    Returns ``(kind, auto_detected)``.
    """
    explicit = str(kind or "").strip()
    if explicit and explicit not in INTAKE_KINDS:
        return "missing_lesson", False
    problem_text = f"{problem or ''} {what_tried or ''}"
    structured_failure = bool(error or fix or verification)
    is_question = looks_like_question(problem_text) and not structured_failure and not has_failure_evidence(problem_text)
    if explicit in ("", "missing_lesson"):
        if is_question:
            return "question", True
        return "missing_lesson", False
    return explicit, False


if __name__ == "__main__":  # pragma: no cover
    import sys

    for line in sys.stdin:
        kind, problem = line.rstrip("\n").split("\t", 1)
        print(infer_intake_kind(kind=kind, problem=problem))
