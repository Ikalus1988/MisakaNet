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

import re

INTAKE_KINDS = ("missing_lesson", "stale_lesson", "new_lesson_candidate", "question")

QUESTION_HINTS = [
    # English
    r"\bhow (do|can|should|could|would|to|i|we|you|does|did)\b",
    r"\bhow to\b",
    r"\bwhat (is|are|does|should|can|could|would)\b",
    r"\bwhy (does|is|do|are|can|would|did)\b",
    r"\bcan (i|you|we|someone)\b",
    r"\b(is|are) there a (way|better|method)\b",
    r"\btips?\b",
    r"\bguid(e|ance|elines?)\b",
    r"\brecommend\b",
    r"\bhelp (me|with)?\b",
    # Portuguese
    r"\bcomo (fazer|resolver|configurar|usar|evitar|sair|sigo|guio|posso|fa[çc]o|devo)\b",
    r"\bpor que\b",
    r"\bpor qu[eê]\b",
    r"\bo que (é|e|fazer|devo|posso)\b",
    r"\bqual (é|e) (a|o|melhor)\b",
    r"\bajuda\b",
    r"\bdicas?\b",
    r"\bconselho\b",
    r"\bmaneira de\b",
    r"\bforma de\b",
    # Spanish
    r"\bc[oó]mo (hago|puedo|configuro|resuelvo|evito|salgo|debo)\b",
    r"\bpor qu[ée]\b",
    r"\bqu[ée] (es|hago|puedo|debo)\b",
    r"\bayuda\b",
    r"\bconsejo\b",
    # Chinese
    r"怎么|如何|为什么|请问|怎样|该(怎么|如何)|能不能",
    # Generic trailing question mark
    r"\?\s*$",
]

# Inline *error evidence* in the problem text — narrow on purpose. Broad
# failure words ("failed", "timeout", "failure") are too topic-y ("how do I
# structure a failure lesson?" is a question, not an error report), while a
# pasted traceback / error code / "Error:" prefix means real failure content
# that must keep the missing_lesson route even if phrased as a question.
FAILURE_HINTS = [
    r"\b(traceback|segfault|stack ?trace)\b",
    r"\bexception\b",
    r"\b(enoent|econnrefused|eacces|eperm|econnreset|econnaborted)\b",
    r"(?:^|\n)\s*(?:error|fatal|critical|panic|failed to)[:\s]",
    r"报错|异常|崩溃|堆栈",
]

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
