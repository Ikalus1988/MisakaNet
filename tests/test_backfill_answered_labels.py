#!/usr/bin/env python3
"""`scripts/backfill_answered_labels.py` — which issues it would label, and which it must not.

Why a test for a labelling script
---------------------------------
The label is the **only** entry point to `sync_answered_questions.py`: an unlabelled answer is
invisible to search forever. So both directions of a mistake are expensive:

* labelling an issue whose thread has no answer puts a non-answer into the FAQ corpus — agents would
  then be served "here is a question nobody answered" as an answer;
* skipping one that does have an answer is the silence this script exists to end.

The rule is not restated here. The test checks that the script *cannot disagree* with the sync: it
must call `extract_answer`, the same function the sync uses, rather than looking for markers itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import backfill_answered_labels as backfill  # noqa: E402


def issue(number, labels, comments):
    return {"number": number, "title": f"issue {number}", "closedAt": "2026-10-01T00:00:00Z",
            "labels": [{"name": n} for n in labels], "comments": comments}


ANSWER = {"body": "<!-- misakanet-answer -->\nUse the header form.", "createdAt": "2026-10-02T00:00:00Z", "id": 1}
BOT = {"body": "<!-- misakanet-intake-triage -->\nTriaged.", "createdAt": "2026-10-01T00:00:00Z", "id": 2}
PLAIN = {"body": "thanks for reporting", "createdAt": "2026-10-01T00:00:00Z", "id": 3}


def test_an_unlabelled_issue_with_a_real_answer_is_a_candidate(monkeypatch):
    monkeypatch.setattr(backfill, "gh_json", lambda _a: [issue(1, ["question"], [BOT, ANSWER])])
    rows = backfill.candidates()
    assert [r["number"] for r in rows] == [1]
    assert rows[0]["answer_chars"] > 0


def test_an_already_labelled_issue_is_not_reported(monkeypatch):
    monkeypatch.setattr(backfill, "gh_json", lambda _a: [issue(2, ["question", "answered"], [ANSWER])])
    assert backfill.candidates() == []


def test_a_thread_with_no_answer_is_not_labelled(monkeypatch):
    # The four issues the real run left alone. Labelling them would serve a question as an answer.
    monkeypatch.setattr(backfill, "gh_json", lambda _a: [issue(3, ["question"], [BOT, PLAIN])])
    assert backfill.candidates() == []


def test_the_automated_markers_are_not_answers(monkeypatch):
    # `question_autopilot`'s receipt is explicitly not an answer; `extract_answer` encodes that, and
    # this script must inherit the rule rather than restate it.
    autopilot = {"body": "<!-- misakanet-question-autopilot -->\nCoverage report.", "createdAt": "x", "id": 4}
    monkeypatch.setattr(backfill, "gh_json", lambda _a: [issue(4, ["question"], [autopilot])])
    assert backfill.candidates() == []


def test_it_reports_without_applying_by_default(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(backfill, "gh_json", lambda _a: [issue(5, ["question"], [ANSWER])])
    monkeypatch.setattr(backfill, "label", lambda n: calls.append(n) or True)
    assert backfill.main([]) == 0
    assert calls == [], "the default run must not touch GitHub"
    assert "#    5" in capsys.readouterr().out


def test_apply_labels_every_candidate(monkeypatch):
    labelled = []
    monkeypatch.setattr(backfill, "gh_json",
                        lambda _a: [issue(6, ["question"], [ANSWER]), issue(7, ["question"], [ANSWER])])
    monkeypatch.setattr(backfill, "label", lambda n: labelled.append(n) or True)
    assert backfill.main(["--apply"]) == 0
    assert labelled == [6, 7]


def test_a_failed_label_is_reported_and_exits_non_zero(monkeypatch):
    monkeypatch.setattr(backfill, "gh_json", lambda _a: [issue(8, ["question"], [ANSWER])])
    monkeypatch.setattr(backfill, "label", lambda _n: False)
    assert backfill.main(["--apply"]) == 1
