#!/usr/bin/env python3
"""The published benchmark claim has to match what the script measures — and it did not.

Measured 2026-09-25. `README.md` said:

    | Hit rate | share of failure questions answered correctly | the only number that decides whether this
      corpus is worth a search |
    Weekly benchmark on real failure scenarios

and the implementation (`scripts/benchmark_workers_ai.py`) says something else, in three verifiable steps:

* `load_all_scenarios()` builds each "scenario" from the lesson's **own title** (`scene = (title or problem)`,
  then `f"{scene} ({md.stem})"`), not from a failure a user would type. The artifact agrees with the code:
  `docs/benchmarks/latest.json`'s `scenarios` begins "A growing agent-knowledge project can accumulate many
  valid directions at once…", which is a lesson title;
* `load_lesson_context()` recovers the stem from that scenario string and returns **the same lesson** as the
  "retrieved" context;
* `score_response()` counts how many of *that* lesson's commands (or long words inside them) appear in the
  answer, and nothing in the script calls a search or retrieval path at all.

So the "42% → 73%" pair measures how much of a document the model repeats when handed it. That is the
recitation half of RAG: necessary, and it is not evidence that search finds anything, because no search runs.
`docs/maintainer/capability-inventory-new-user-2026-09-18.md` had already recorded exactly this ("是（同一
脚本既出题又打分）"); it had never reached the public surface, which is what this file and the README change fix.

The rules below are about that link rather than about wording:

* the one-sentence definition lives in the script (`METRIC_SUMMARY`) and the public claim surface must carry it
  **verbatim**, so a change to the metric has to move the claim with it;
* the two retracted phrases may not come back anywhere a reader finds them;
* the claim that the scenario is the lesson's own title is asserted **only while the code does that** — if
  someone makes the benchmark derive scenarios from real failure text, this file says so instead of quietly
  passing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.benchmark_workers_ai import METRIC_DEFINITION, METRIC_SUMMARY  # noqa: E402

SCRIPT = REPO / "scripts" / "benchmark_workers_ai.py"
README = REPO / "README.md"
ARTIFACT = REPO / "docs" / "benchmarks" / "latest.json"

# The claims that were retracted on 2026-09-25. They may not reappear without the metric changing first.
RETRACTED = (
    "share of failure questions answered correctly",
    "Weekly benchmark on real failure scenarios",
    "RAG win across the board",
)
# How the README describes the scenario source while `load_all_scenarios` derives it from the title.
SCENARIO_CLAIM = "the scenario in this benchmark is each lesson's own title"


def test_the_summary_is_one_sentence_and_is_inside_the_full_definition():
    assert METRIC_SUMMARY and "\n" not in METRIC_SUMMARY
    assert METRIC_SUMMARY in METRIC_DEFINITION, METRIC_DEFINITION
    assert "no retrieval call" in METRIC_DEFINITION, (
        "the definition must say what is *not* measured; that is the half a reader gets wrong")


def test_the_public_claim_carries_the_scripts_own_sentence():
    """The number is quoted in the README; the sentence that defines it must be there too."""
    text = README.read_text(encoding="utf-8")
    assert METRIC_SUMMARY in text, (
        f"README.md quotes the benchmark's hit rate without its definition. Add the sentence from "
        f"`METRIC_SUMMARY` ({METRIC_SUMMARY!r}) — it is the SSOT, so the claim moves when the metric does")


def test_the_retracted_phrases_are_gone_from_the_public_surface():
    offenders = []
    for path in [README, *sorted((REPO / "docs").rglob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        for phrase in RETRACTED:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO)}: {phrase!r}")
    assert not offenders, (
        "these claims were retracted when the metric was read closely (the metric counts commands of the "
        "lesson that was pasted in; no retrieval happens and correctness is not checked):\n  - "
        + "\n  - ".join(offenders))


def test_the_scenario_claim_is_asserted_only_while_the_code_derives_scenarios_from_titles():
    """A claim that outlives its implementation is how this file's subject happened in the first place."""
    code = SCRIPT.read_text(encoding="utf-8")
    derives_from_title = "scene = (title or problem)" in code
    claims_it = SCENARIO_CLAIM in README.read_text(encoding="utf-8")
    if derives_from_title:
        assert claims_it, (
            "`load_all_scenarios` still builds scenarios from lesson titles, so README must keep saying so "
            f"({SCENARIO_CLAIM!r})")
    else:
        assert not claims_it, (
            "the script no longer derives scenarios from lesson titles — update or drop the README sentence "
            f"({SCENARIO_CLAIM!r})")


def test_the_script_labels_the_number_where_it_is_written_and_where_it_is_read():
    code = SCRIPT.read_text(encoding="utf-8")
    assert 'data["metric_definition"] = METRIC_DEFINITION' in code, (
        "the artifact must carry the definition: this JSON has been quoted as evidence that retrieval works")
    assert "print(f\"\\nℹ️  What `lesson_hit_rate` is: {METRIC_DEFINITION}\")" in code, (
        "a run must print what its number means, or the number is read alone")


def test_the_artifact_that_was_quoted_carries_the_definition():
    """The file the README links to predates this change; it may lack the field, but not forever."""
    if not ARTIFACT.is_file():
        pytest.skip("no docs/benchmarks/latest.json in this checkout")
    import json

    data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert data.get("scenarios"), "the artifact has no scenarios to inspect"
    if "metric_definition" in data:
        assert data["metric_summary"] == METRIC_SUMMARY or METRIC_SUMMARY in data["metric_definition"]


def test_the_rule_notices_a_retracted_claim(tmp_path):
    """Guard the guard: the three phrases are what this file was written against."""
    fixture = tmp_path / "x.md"
    fixture.write_text("Weekly benchmark on real failure scenarios\n", encoding="utf-8")
    text = fixture.read_text(encoding="utf-8")
    assert any(phrase in text for phrase in RETRACTED)
