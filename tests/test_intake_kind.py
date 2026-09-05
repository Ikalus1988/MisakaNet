"""Kind inference tests for question-vs-failure intake routing (#1396).

Covers ``scripts.intake_kind`` (the Python mirror of the worker's
``inferIntakeKind``) plus the routing glue in ``scripts.mcp_http_server``
(no-match suggestion differentiation).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.intake_kind import (  # noqa: E402
    INTAKE_KINDS,
    has_failure_evidence,
    infer_intake_kind,
    looks_like_question,
)


# ── infer_intake_kind ──

@pytest.mark.parametrize("problem", [
    "How do I set up the MCP server on Windows?",
    "What is the best way to structure a failure lesson?",
    "Why does my agent keep looping?",
    "Can you recommend a pattern for narrative guidance?",
    "Need help with MCP auth setup",
    "Como faço para guiar os personagens para fora de um loop narrativo?",
    "Por que o agente entra em conflito repetitivo?",
    "¿Cómo puedo configurar la autenticación MCP?",
    "怎么配置 MCP 服务器认证？",
    "如何避免角色进入叙事循环？",
])
def test_question_phrasing_routes_to_question(problem):
    kind, auto = infer_intake_kind(problem=problem)
    assert kind == "question"
    assert auto is True


@pytest.mark.parametrize("kwargs", [
    {"problem": "pip install times out on corporate proxy", "error": "ReadTimeout"},
    {"problem": "tool crashed with ENOENT on Windows"},
    {"problem": "personagens entram em conflito repetitivo"},  # no question signal
    {"problem": "DCO sign-off failed in CI"},
    {"problem": "报错：pip install 超时"},
    # question phrasing + pasted inline error text (no structured error field)
    # must NOT be re-routed — a traceback means real failure content.
    {"problem": "How to fix this?\nTraceback (most recent call last):\n  File x.py"},
    {"problem": "Why does this error keep appearing?\nError: EACCES permission denied"},
])
def test_failure_content_stays_missing_lesson(kwargs):
    kind, auto = infer_intake_kind(**kwargs)
    assert kind == "missing_lesson"
    assert auto is False


def test_explicit_question_kind_never_marked_auto():
    kind, auto = infer_intake_kind(kind="question", problem="anything at all")
    assert kind == "question"
    assert auto is False


def test_explicit_missing_lesson_with_question_content_is_rerouted():
    kind, auto = infer_intake_kind(
        kind="missing_lesson",
        problem="How do I guide characters out of a narrative loop?",
    )
    assert kind == "question"
    assert auto is True


def test_explicit_missing_lesson_with_failure_evidence_is_kept():
    kind, auto = infer_intake_kind(
        kind="missing_lesson",
        problem="How do I fix the crash?",
        error="segfault at 0x0",
    )
    assert kind == "missing_lesson"
    assert auto is False


def test_other_explicit_kinds_are_never_overridden():
    kind, auto = infer_intake_kind(kind="stale_lesson", problem="How do I update this?")
    assert (kind, auto) == ("stale_lesson", False)
    kind, auto = infer_intake_kind(kind="new_lesson_candidate", problem="Question here?")
    assert (kind, auto) == ("new_lesson_candidate", False)


def test_invalid_kind_falls_back_to_missing_lesson():
    kind, auto = infer_intake_kind(kind="totally-unknown", problem="x")
    assert (kind, auto) == ("missing_lesson", False)


def test_kind_whitelist():
    assert set(INTAKE_KINDS) == {"missing_lesson", "stale_lesson", "new_lesson_candidate", "question"}


# ── helpers ──

def test_looks_like_question_and_failure_evidence_are_disjoint_signals():
    assert looks_like_question("How do I fix a timeout?")
    assert not looks_like_question("pip install times out")
    # Broad failure words are NOT evidence; inline error text IS.
    assert not has_failure_evidence("pip install times out")
    assert has_failure_evidence("Traceback (most recent call last):")
    assert has_failure_evidence("Error: ENOENT no such file")
    assert not has_failure_evidence("how to structure a lesson")


# ── mcp_http_server no-match feedback (#1396) ──

def _no_match_feedback(query):
    """Thin wrapper — import lazily so FastMCP startup cost stays out of tests."""
    from scripts.mcp_http_server import _no_match_feedback as fb
    return fb(query)


def test_no_match_feedback_question_query_suggests_question_kind():
    fb = _no_match_feedback("How do I configure MCP authentication?")
    assert fb["no_match"] is True
    assert "kind=\"question\"" in fb["suggestion"]
    assert fb["intake"]["args"]["kind"] == "question"


def test_no_match_feedback_failure_query_suggests_missing_lesson():
    fb = _no_match_feedback("pip install timeout on corporate proxy")
    assert fb["no_match"] is True
    assert "kind=\"missing_lesson\"" in fb["suggestion"]
    assert fb["intake"]["args"]["kind"] == "missing_lesson"
    assert fb["intake"]["args"]["error"] == "pip install timeout on corporate proxy"
