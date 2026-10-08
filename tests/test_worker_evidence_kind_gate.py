"""The evidence-kind filter must read the evidence scale the corpus actually uses.

`isEvidenceResult` tested for the literal words `verified` / `confirmed` / `high`, which occur in
zero of the lessons — trust is graded E0–E4. Its fallback read `content`/`description`/`summary`,
and `compactResult` (the default detail level) emits none of those; it emits `problem`, truncated to
120 characters, which is the Problem section and never the Verification one. So the filter returned
false for **every** result and an evidence-intent query returned nothing at all — not just no FAQ.

These tests evaluate the function **as written in the worker**: the constants and the function body
are extracted from the source and handed to node. A copy here would keep passing after someone edits
the worker.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"
CORPUS = REPO / "data" / "lessons.json"

# The scale, from misakanet/evidence.py and docs/evidence-badges.md.
# E0 self-reported · E1 maintainer reviewed · E2 local smoke reproduced
# E3 sandbox/CI verified recovery · E4 reused successfully by another contributor or agent
BELOW_THE_LINE = ["E0", "E1"]
AT_OR_ABOVE = ["E2", "E3", "E4"]


def _source_parts() -> dict[str, str]:
    src = WORKER.read_text(encoding="utf-8")
    rank = re.search(r"const EVIDENCE_RANK = (\{.*?\});", src, re.S)
    floor = re.search(r"const EVIDENCE_MIN_RANK = (\d+);", src)
    fn = re.search(r"function isEvidenceResult\(r\) \{.*?\n\}", src, re.S)
    assert rank, "EVIDENCE_RANK is not declared — the filter cannot read the E scale"
    assert floor, "EVIDENCE_MIN_RANK is not declared — the floor is inlined somewhere"
    assert fn, "could not locate isEvidenceResult"
    return {"rank": rank.group(1), "floor": floor.group(1), "fn": fn.group(0)}


def _call(cases: list[dict]) -> list[bool]:
    parts = _source_parts()
    script = (
        f"const EVIDENCE_RANK = {parts['rank']};\n"
        f"const EVIDENCE_MIN_RANK = {parts['floor']};\n"
        f"{parts['fn']}\n"
        "const cases = JSON.parse(process.argv[1]);\n"
        "console.log(JSON.stringify(cases.map(isEvidenceResult)));"
    )
    out = subprocess.run(["node", "-e", script, json.dumps(cases)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def compact_lesson() -> dict:
    """Exactly the field set `compactResult` emits — the default detail level.

    Deliberately has no `content`/`description`/`summary`, which is the whole point: the fallback
    that used to carry this function could not see anything.
    """
    return {"id": "x", "title": "t", "problem": "the first 120 chars", "freshness": "1d",
            "evidence_level": "E2", "score": 19.12}


def test_e0_and_e1_are_not_evidence():
    results = _call([{"evidence_level": lv} for lv in BELOW_THE_LINE])
    assert results == [False, False], (
        "E0 is self-reported and E1 is only 'a maintainer accepted the intake' — neither is what "
        "验证/verification asks for, so neither may pass the evidence filter"
    )


def test_e2_and_above_are_evidence():
    results = _call([{"evidence_level": lv} for lv in AT_OR_ABOVE])
    assert results == [True, True, True], (
        "E2 is the first level where somebody other than the author ran it"
    )


def test_a_compact_result_still_passes_on_its_level(compact_lesson):
    """The regression: at the default detail level the fallback had nothing to read."""
    assert _call([compact_lesson]) == [True]


def test_explicit_evidence_refs_win_regardless_of_level():
    assert _call([{"evidence_level": "E0", "evidence_refs": [{"type": "reuse", "count": 3}]}]) == [True]


def test_the_word_forms_are_still_accepted():
    """Non-lesson producers may use words rather than levels; do not break them."""
    assert _call([{"evidence_level": "verified"}, {"evidence_level": "CONFIRMED"}]) == [True, True]


def test_a_missing_level_is_not_evidence():
    """An FAQ row carries no evidence_level. Unchanged by this fix — and asserted on purpose."""
    assert _call([{}]) == [False]


def test_every_level_the_corpus_actually_uses_is_handled():
    levels = {row.get("evidence_level") for row in json.loads(CORPUS.read_text(encoding="utf-8"))}
    assert levels, "could not read the corpus"
    unknown = sorted(lv for lv in levels if lv and lv.lower() not in _source_parts()["rank"].lower())
    assert not unknown, f"the corpus uses evidence levels the filter does not know: {unknown}"


def test_mutating_the_floor_makes_the_boundary_lesson_fail():
    """Guards the constant: if EVIDENCE_MIN_RANK moves, this test notices what it cost."""
    src = WORKER.read_text(encoding="utf-8")
    mutated = re.sub(r"const EVIDENCE_MIN_RANK = \d+;", "const EVIDENCE_MIN_RANK = 4;", src)
    assert mutated != src, "could not mutate the floor — the test would prove nothing"
    # Parenthesised: a bare `{ … }` at statement position parses as a block, not an object literal.
    script = (
        "const EVIDENCE_RANK = (" + re.search(r"const EVIDENCE_RANK = (\{.*?\});", mutated, re.S).group(1) + ");\n"
        "const EVIDENCE_MIN_RANK = 4;\n"
        + re.search(r"function isEvidenceResult\(r\) \{.*?\n\}", mutated, re.S).group(0) + "\n"
        "console.log(JSON.stringify([isEvidenceResult({evidence_level:'E2'}),"
        "isEvidenceResult({evidence_level:'E4'})]));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
    assert json.loads(out.stdout) == [False, True], (
        "moving the floor to 4 should reject E2 and keep E4 — if this changed, E2 stopped being the "
        "boundary and §42 of the handoff is wrong about where the line sits"
    )