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


def _item(number: int, text: str, title: str = "") -> dict:
    return {"number": number, "title": title or text[:60], "tokens": qa.tokens(text)}


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


# ── the signature must not be boilerplate ───────────────────────────────────

OPIRE_ISSUE = {
    "number": 2166,
    "title": "[Question] When regenerating a PDF from sanitized HTML, which checks verify removal",
    "body": """**Kind:** question
**Source:** codex
**Dedup:** `abc`

## Problem
Which checks verify that removed fields are absent from text, annotations and metadata?

---
_Submitted via remote MCP (codex). No account required._
<br/>
<hr/>

<details><summary>This repo is using Opire - what does it mean? 👇</summary><br/>💵 Everyone can add
rewards for this issue commenting <code>/reward 100</code>.<br/>🕵️ If someone starts working on this
issue they can comment <code>/try</code>.<br/>🪙 Also, everyone can tip any user.</details>
""",
}


def test_the_opire_banner_is_not_part_of_the_signature():
    """Every issue carries that `<details>` banner, so leaving it in gives every question the same words.

    Found by reading the autopilot's own output: the "shared vocabulary" of a generated bounty task was
    `add`, `everyone`, `fields` — the banner's words, not the questions'. A clustering step fed
    corpus-wide boilerplate clusters on nothing.
    """
    sig = qa.signature(OPIRE_ISSUE)
    for leaked in ("everyone", "reward", "claim", "tip", "opire", "documentation"):
        assert leaked not in sig.lower(), f"{leaked!r} leaked in from the Opire banner: {sig[:200]!r}"
    assert "removed fields are absent" in sig, "stripping the banner also removed the problem statement"


def test_html_leftovers_do_not_reach_the_signature():
    sig = qa.signature(OPIRE_ISSUE)
    assert "<" not in sig and ">" not in sig, sig[:200]
    assert "submitted via remote mcp" not in sig.lower()


# ── a task may only tell a contributor to run commands that exist ───────────

def test_every_script_named_in_the_bounty_body_exists():
    """The autopilot writes instructions for other people; it must not invent a command.

    The first generated body said `python3 scripts/provenance_gate.py --check`. There is no such file —
    the real one is `scripts/check_provenance.py` — and nobody would have noticed until a contributor
    reported it, because the task is a document.
    """
    body = qa.bounty_body(2254, [_item(2254, "secret-safe validation"), _item(2257, "secret-safe metadata")],
                          ["secret-safe"])
    named = sorted(set(qa.re.findall(r"scripts/[A-Za-z0-9_./-]+\.py", body)))
    assert named, "expected the task to name the repository's own gates"
    missing = [n for n in named if not (REPO / n).is_file()]
    assert not missing, f"the task tells contributors to run scripts that do not exist: {missing}"


def test_the_task_satisfies_the_quality_gates_own_criteria():
    """`issue-quality-gate.yml` grants `ready` only with an AC section *and* a checkbox list."""
    body = qa.bounty_body(2254, [_item(2254, "a"), _item(2257, "b")], [])
    assert qa.re.search(r"acceptance criteria|AC|验收标准|MANDATORY", body, qa.re.I), "no AC section"
    assert qa.re.search(r"\[ \]|\[x\]|\[X\]", body), "no checkbox list — the gate would label it needs-ac"


def test_the_task_states_the_payment_terms_plainly():
    """`JOIN.md`: zero-bounty is the design, not an omission. A task must not imply it pays."""
    body = qa.bounty_body(2254, [_item(2254, "a"), _item(2257, "b")], [])
    assert "$0" in body and "zero-bounty" in body
    assert "/reward" in body, "a reader who wants it funded must be told how"
    assert "JOIN.md" in body, "the terms live in JOIN.md; cite them"


def test_the_task_carries_its_idempotency_marker():
    body = qa.bounty_body(2254, [_item(2254, "a"), _item(2257, "b")], [])
    assert qa.BOUNTY_MARKER.format(2254) in body


def test_a_lone_question_is_not_given_a_bounty():
    """A cluster is the unit one answer clears, and one question is not a cluster.

    Two shapes of "no cluster": no groups at all, and a group that happens to hold a single member. Only
    the second one exercises the length check — the first version of this test used only the first, so
    lowering the threshold from 2 to 1 went unnoticed.
    """
    items = [{"number": 1, "title": "a", "tokens": {"a"}}, {"number": 2, "title": "b", "tokens": {"b"}}]
    assert qa.planned_bounties({"items": items, "groups": []}) == []
    assert qa.planned_bounties({"items": items, "groups": [{"members": [1], "shared": []}]}) == []


def test_a_cluster_produces_exactly_one_bounty_anchored_at_its_lowest_number():
    plan = {"items": [{"number": 2264, "title": "x", "tokens": set()},
                      {"number": 2266, "title": "y", "tokens": set()}],
            "groups": [{"members": [2264, 2266], "shared": ["cli"]}]}
    got = qa.planned_bounties(plan)
    assert len(got) == 1 and got[0]["anchor"] == 2264


# ── the digest is a report, and the quality gate must know it ───────────────

def _gate_exempt_labels() -> set[str]:
    """The labels `issue-quality-gate.yml` exempts, parsed from the **list literal**.

    Parsed rather than substring-searched because the first version of this test asserted the label
    appeared anywhere in the file — and the explanatory comment added directly above the list satisfied it,
    so deleting the label from the list itself went unnoticed. This repository has this failure recorded
    ("断言读的是赋值语句而不是整个文件；全文搜索会被自己的解释满足"), and it reproduced here.
    """
    gate = (REPO / ".github/workflows/issue-quality-gate.yml").read_text(encoding="utf-8")
    m = qa.re.search(r"\[([^\]]*?)\]\s*[\n\s]*\.includes\(typeof l", gate)
    assert m, "the exempt-label list is not in the shape this test parses"
    return set(qa.re.findall(r"'([^']+)'", m.group(1)))


def test_the_digest_label_is_exempt_in_the_quality_gate():
    """An unexempt digest collects `needs-ac` forever, which is churn the gate was already burned by.

    `issue-quality-gate.yml`'s own comment records the incident: five of six `needs-ac` issues were once
    intakes, "including a salvage digest the workflow itself opened". The gate exempts a fixed label list,
    so a new automatic report has to be added to it — in the same change that starts opening one.
    """
    labels = _gate_exempt_labels()
    assert labels, "parsed no exempt labels at all — the test would pass for the wrong reason"
    assert qa.DIGEST_LABEL in labels, (
        f"{qa.DIGEST_LABEL!r} is not in the quality gate's exempt list ({sorted(labels)}), so every digest "
        "it opens will be labelled `needs-ac` and sit in the tracker as missing work"
    )


def test_the_receipt_does_not_claim_a_related_answered_question():
    """The FAQ matcher is token overlap; measured, it attached two unrelated answers to a PDF question."""
    body = qa.receipt({"number": 2255,
                       "coverage": {"ok": True, "no_match": True, "lessons": [],
                                    "faq": [{"issue_url": "https://example.invalid/2099"},
                                            {"issue_url": "https://example.invalid/1724"}]},
                       "cluster_with": []})
    assert "2099" not in body and "1724" not in body, (
        "the receipt pointed the asker at answers the FAQ matcher merely token-overlapped"
    )


def test_the_task_tells_contributors_to_regenerate_the_derived_artifacts():
    """The step that fails CI most often, and the one this task's first version omitted.

    A new lesson makes `data/lessons.json`, the generated pages and the OKF export stale, and three tests
    fail on every platform until they are regenerated — measured 2026-09-26 on the first two lesson PRs
    opened against these tasks (#2299 among them). A task that omits it sets the contributor up to fail,
    so the commands are named rather than described.
    """
    body = qa.bounty_body(2254, [_item(2254, "a"), _item(2257, "b")], [])
    for command in ("scripts/update_lessons_json.py", "scripts/build_lesson_pages.py", "scripts/export_okf.py"):
        assert command in body, f"the task does not tell contributors to run {command} — CI will fail them"
    assert "update_lessons_json.py`\npython3 scripts/build_lesson_pages.py" in body or \
           "update_lessons_json.py" in body, "the order matters and should read as a sequence"
