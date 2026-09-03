"""Historical regression test: question vs lesson discrimination (#1396).

Pins the detector (``scripts.intake_kind.infer_intake_kind``) against real
intake texts drawn from the GitHub history (see
``scripts/audit_intake_kinds.py`` for the full audit):

- Question-shaped intakes that were historically auto-rejected as malformed
  lessons (#1362/#1364/#1365 — explicit kind=question victims of the pre-fix
  lesson auto-review) must be detected as questions.
- Intakes that genuinely became lessons (#1222/#1223 win32/CI failure reports,
  #1381 DCO failure) must never be flipped to question.
- Phrasing-less content (#1396 original PT sentence, #1397) has no question
  signal — the detector deliberately keeps it ``missing_lesson``; these are
  the documented manual-review cases, not detector failures.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.intake_kind import infer_intake_kind  # noqa: E402

# ── questions (historical misfiles: kind=question, auto-rejected pre-fix) ──

QUESTION_HISTORY = [
    # #1362 — dsh-prod-test submission
    "How should agents handle GitHub rate limits on shared runners?",
    # #1364 / #1365 — issue-1363-contract-test submission (ran twice)
    "How do I configure MCP server authentication for production?",
    # #1396 current title problem (EN equivalent of the PT report)
    "How do I guide characters out of repetitive conflict or narrative loops via chat?",
]

# ── real failures that became lessons / must stay failure intakes ──

LESSON_HISTORY = [
    # #1222 → converted to lesson (win32 os.tmpdir ReferenceError)
    'Node.js: missing `require("node:os")` inside `try/catch(_){}` silently '
    "kills entire win32 code path. os.tmpdir() throws ReferenceError, caught "
    'by blanket catch, handler never spawned, test fails with cryptic "marker: '
    "not found\". The catch(_) pattern is intentional fire-and-forget but masks "
    "real import bugs. Fix: ensure all modules used inside try/catch are "
    "imported at top level, or narrow try scope.",
    # #1223 → converted to lesson (Windows CI bug trio)
    "Windows CI: three bugs in one session. (1) splitCommand() strips "
    "backslashes from Windows paths — `C:\\\\hostedtoolcache` becomes "
    "`C:hostedtoolcache` causing ENOENT. The `!isWindows` guard was lost "
    "during rebase/squash. (2) Python subprocess with non-ASCII output "
    "(Chinese chars) fails with UnicodeEncodeError on Windows cp1252. Fix: "
    "set PYTHONIOENCODING=utf-8. (3) detached:true + unref() on Windows does "
    "not survive process.exit() — must use spawnSync for fire-and-forget "
    "children.",
    # #1381 — DCO failure on automated PR submissions
    "Missing Signed-off-by trailer causing DCO check failure on PR "
    "submissions in automated CI environments",
]

# ── phrasing-less content: no signal → missing_lesson (documented limitation) ──

PHRASELESS_HISTORY = [
    # #1396 original PT sentence (no "como"/question marker) — needed human
    # re-triage; keep the failure route until a human decides.
    "personagens entram em conflito repetitivo ou loops narrativos difíceis "
    "de guiar pelo chat comum",
    # #1397 — PT memory-summarizer report, same batch as #1396
    "O sumarizador de memória utilizava o modelo padrão do chat ou de "
    "extrações sem valor inicial específico para o ministral-8b-2512 e sem "
    "interface dedicada rápida no painel de memória.",
]


@pytest.mark.parametrize("text", QUESTION_HISTORY)
def test_historical_questions_detect_as_question(text):
    kind, auto = infer_intake_kind(problem=text)
    assert kind == "question", f"expected question, got {kind}: {text[:80]}"
    assert auto is True


@pytest.mark.parametrize("text", LESSON_HISTORY)
def test_historical_lesson_intakes_never_flip_to_question(text):
    kind, auto = infer_intake_kind(kind="missing_lesson", problem=text)
    assert kind == "missing_lesson", f"lesson intake flipped to {kind}: {text[:80]}"
    assert auto is False


@pytest.mark.parametrize("text", PHRASELESS_HISTORY)
def test_phrasingless_content_stays_missing_lesson_until_human(text):
    """No question phrasing → kept as failure intake (documented limitation).
    These are exactly the cases the audit flags for human review, not for the
    detector to guess on."""
    kind, auto = infer_intake_kind(kind="missing_lesson", problem=text)
    assert kind == "missing_lesson"
    assert auto is False
