#!/usr/bin/env python3
"""The question autopilot must triage without ever answering, and must not cry wolf while doing it.

Two failure modes matter more here than in most scripts, because its output is public:

* **claiming coverage it did not measure.** An unreachable endpoint must come back `unknown`, never
  "the corpus has nothing on this" — the second is the one verdict a human acts on.
* **collapsing every question into one cluster.** The first version did exactly that (one 12-member
  group) because it shared a hand-written stopword list instead of measuring which tokens distinguish
  anything; the sweep that fixed it is recorded above `CLUSTER_MIN_SHARED`.

And one structural property: the receipt must be registered as an automated marker, or the sync script
would store a triage comment in D1 as if a maintainer had answered.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

spec = importlib.util.spec_from_file_location("question_autopilot", REPO / "scripts" / "question_autopilot.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)

from scripts.sync_answered_questions import AUTOMATED_MARKERS, ANSWER_MARKERS, extract_answer  # noqa: E402


def _item(number: int, text: str) -> dict:
    return {"number": number, "tokens": qa.tokens(text)}


# ── coverage verdicts ───────────────────────────────────────────────────────

def test_an_unreachable_endpoint_is_unknown_not_uncovered(monkeypatch):
    def dead(*_a, **_k):
        raise ConnectionResetError("connection reset by peer")

    monkeypatch.setattr(qa.urllib.request, "urlopen", dead)
    result = qa.corpus_answers("anything")
    assert result["ok"] is False
    assert result["no_match"] is None, "an unreachable endpoint reported a coverage verdict"
    assert result["lessons"] == [] and result["faq"] == []


def test_an_unparseable_body_is_unknown_too(monkeypatch):
    class Resp:
        def read(self): return b'{"result":{"content":[{"text":"not json"}]}}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(qa.urllib.request, "urlopen", lambda *a, **k: Resp())
    assert qa.corpus_answers("q")["ok"] is False


def test_faq_hits_are_not_counted_as_lesson_coverage(monkeypatch):
    payload = ('{"no_match": false, "results": ['
               '{"id": "faq-issue-1", "type": "faq"}, {"id": "real-lesson", "type": "lesson"}]}')
    class Resp:
        def read(self): return ('{"result":{"content":[{"text":%s}]}}' % qa.json.dumps(payload)).encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(qa.urllib.request, "urlopen", lambda *a, **k: Resp())
    got = qa.corpus_answers("q")
    assert got["ok"] and [r["id"] for r in got["lessons"]] == ["real-lesson"]
    assert [r["id"] for r in got["faq"]] == ["faq-issue-1"]


# ── clustering ──────────────────────────────────────────────────────────────

def test_two_questions_on_the_same_subject_cluster():
    items = [
        _item(2255, "How should Chrome headless PDF generation be supervised on macOS when the PDF file "
                    "is written but the process does not exit before a 40 second timeout"),
        _item(2259, "What causes macOS Chrome headless print-to-pdf to remain alive after writing a "
                    "complete local PDF and which supported flags allow clean termination"),
    ]
    qa.distinctive(items)
    groups = qa.cluster(items)
    assert groups and groups[0]["members"] == [2255, 2259], groups


def test_two_unrelated_questions_do_not_cluster():
    items = [
        _item(2169, "What is the least disruptive way to pause and later resume a detached Git "
                    "maintenance loose-objects pack-objects process that saturates many CPU cores"),
        _item(2266, "For Codex CLI on macOS with cli_auth_credentials_store=keyring which supported "
                    "read-only checks distinguish item access-control denial"),
    ]
    qa.distinctive(items)
    assert qa.cluster(items) == []


def test_complete_linkage_does_not_chain():
    """The regression that made the first version useless: 12 questions in one cluster.

    Calls `cluster()` **without** `distinctive()`, because the property under test is the linkage rule,
    not the token filter — the first version of this test built a chain whose shared tokens the filter
    then removed, so it passed trivially and a single-linkage mutation went unnoticed. Here 1-2 share
    three tokens and 2-3 share three, but 1-3 share only two: single linkage merges all three, complete
    linkage must not.
    """
    items = [
        {"number": 1, "tokens": {"p", "q", "r", "s"}},
        {"number": 2, "tokens": {"p", "q", "r", "t"}},
        {"number": 3, "tokens": {"p", "q", "t", "u"}},
    ]
    groups = qa.cluster(items)
    assert [g["members"] for g in groups] == [[1, 2]], groups
    for group in groups:                      # ...and the invariant that makes it meaningful
        for i in group["members"]:
            for j in group["members"]:
                if i == j:
                    continue
                a = next(x for x in items if x["number"] == i)["tokens"]
                b = next(x for x in items if x["number"] == j)["tokens"]
                assert len(a & b) >= qa.CLUSTER_MIN_SHARED, (i, j, sorted(a & b))


def test_a_token_in_most_questions_is_dropped():
    items = [_item(n, f"macos configuration check token{n}") for n in range(1, 9)]
    qa.distinctive(items)
    assert all("macos" not in i["tokens"] for i in items), "a token in >25% of questions still separates"


# ── the receipt must never be mistaken for an answer ────────────────────────

def test_the_receipt_marker_is_registered_as_automated():
    assert qa.RECEIPT_MARKER in AUTOMATED_MARKERS, (
        "the autopilot's receipt is not registered as an automated marker, so a comment carrying it plus "
        "an answer marker would be stored in D1 as a maintainer answer"
    )


def test_a_receipt_comment_is_never_extracted_as_the_answer():
    receipt = qa.receipt({"number": 1, "coverage": {"ok": True, "no_match": True, "lessons": [], "faq": []},
                          "cluster_with": []})
    assert qa.RECEIPT_MARKER in receipt
    # Even if a maintainer pastes the receipt under an answer marker, it must still be skipped.
    comments = [{"body": "<!-- misakanet-answer -->\n" + receipt,
                 "user": {"login": "maintainer"}, "id": 1, "created_at": "2026-01-01T00:00:00Z"}]
    answer, _, _ = extract_answer(comments)
    assert answer is None, "a triage receipt was extracted as a maintainer answer"


def test_the_receipt_states_the_verdict_and_the_next_step():
    gap = qa.receipt({"number": 1, "coverage": {"ok": True, "no_match": True, "lessons": [], "faq": []},
                      "cluster_with": []})
    assert "no lesson in the corpus covers this" in gap
    assert "Next step" in gap

    covered = qa.receipt({"number": 2, "coverage": {"ok": True, "no_match": False,
                                                    "lessons": [{"id": "some-lesson"}], "faq": []},
                          "cluster_with": []})
    assert "appears to answer this already" in covered and "`some-lesson`" in covered

    unknown = qa.receipt({"number": 3, "coverage": {"ok": False, "no_match": None, "lessons": [], "faq": []},
                          "cluster_with": []})
    assert "not measured yet" in unknown
    assert "genuine gap" not in unknown and "no lesson" not in unknown


def test_a_question_with_no_body_is_still_triaged():
    """#1966 arrived with an empty Problem section; the signature must not blow up on it."""
    issue = {"number": 1966, "title": "[Question] Problem An agent driving a browser SHARED with the human",
             "body": "**Kind:** question\n**Source:** claude-code\n"}
    sig = qa.signature(issue)
    assert sig, "an empty Problem section produced an empty signature"
    assert "Source" not in sig, "the metadata lines are being searched as if they were content"
