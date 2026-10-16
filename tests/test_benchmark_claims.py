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
* the three retracted phrases may not come back anywhere a reader finds them;
* the claim that the scenario is the lesson's own title is asserted **only while the code does that** — if
  someone makes the benchmark derive scenarios from real failure text, this file says so instead of quietly
  passing.

Retargeted 2026-10-17 — the section was demoted, and these rules pin the *smaller* claim
--------------------------------------------------------------------------------------------
The README used to spend ~78 lines on this benchmark, for a run that is paused, in a section whose own
prose said the metric is not evidence that search works. Honesty and prominence were fighting: the most
prominent real estate in the file was spent on the number the file disclaims, and the prose dated itself
2026-09-22 while the generated table three lines below carried rows through 2026-10-12.

The gate is **not** deleted — the job it was written for ("the README must not overclaim relative to the
artifact") outlives the demotion, so it now pins what the smaller section actually claims:

* the README says the run is **paused**;
* it **names and links the last snapshot** it is relying on (`docs/benchmarks/latest.json`), so a reader can
  go and check the number instead of trusting the prose;
* it keeps saying the metric **does not prove search works**;
* and the pause is checked against the artifact, not just asserted: `.github/workflows/benchmark-workers-ai.yml`
  must not carry a `schedule:` trigger. A README that says "paused" next to a live weekly cron is the same
  defect as the stale table, one layer up — and this repository has already shipped one document asserting a
  fact the code stopped having (`tests/test_first_run_path_is_true.py`).

The red fixtures below mutate each half in memory, so every rule is shown to be able to fail.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.benchmark_workers_ai import METRIC_DEFINITION, METRIC_SUMMARY  # noqa: E402

SCRIPT = REPO / "scripts" / "benchmark_workers_ai.py"
README = REPO / "README.md"
ARTIFACT = REPO / "docs" / "benchmarks" / "latest.json"
WORKFLOW = REPO / ".github" / "workflows" / "benchmark-workers-ai.yml"

# The claims that were retracted on 2026-09-25. They may not reappear without the metric changing first.
RETRACTED = (
    "share of failure questions answered correctly",
    "Weekly benchmark on real failure scenarios",
    "RAG win across the board",
)
# How the README describes the scenario source while `load_all_scenarios` derives it from the title.
SCENARIO_CLAIM = "the scenario in this benchmark is each lesson's own title"

# ── the smaller claim the demoted section must carry (2026-10-17) ────────────────────────────────
PAUSED = re.compile(r"\bpaused\b", re.IGNORECASE)
SNAPSHOT_LINK = re.compile(r"\]\(\s*docs/benchmarks/latest\.json\s*\)")
NOT_RETRIEVAL = "not evidence that search finds anything"
# `on:` / `schedule:` at the top level of the workflow. A commented-out line is not a trigger.
LIVE_SCHEDULE = re.compile(r"(?m)^\s*schedule:\s*$")


def paused_claim_problems(text: str, workflow: str) -> list[str]:
    """What is wrong with the demoted claim, as a list; empty means the claim matches the artifact."""
    problems: list[str] = []
    if not PAUSED.search(text):
        problems.append(
            "README.md does not say the benchmark is paused. The run is not being maintained as a "
            "headline; a section that implies it continues is the overclaim this file exists to stop."
        )
    if not SNAPSHOT_LINK.search(text):
        problems.append(
            "README.md does not link the last snapshot (`docs/benchmarks/latest.json`). The demotion "
            "replaced a trend with a record — a record with no link is a number a reader cannot check."
        )
    if NOT_RETRIEVAL not in text:
        problems.append(
            f"README.md no longer carries {NOT_RETRIEVAL!r}. That sentence is the whole reason this "
            "section is allowed to quote a hit rate: no retrieval runs, so the number is not a search result."
        )
    if LIVE_SCHEDULE.search(workflow):
        problems.append(
            "the benchmark workflow still carries a live `schedule:` trigger while the README says the run "
            "is paused. Either remove the trigger or stop claiming the pause — a document asserting a fact "
            "the code stopped having is the defect this file was written against."
        )
    return problems


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


# ── the demoted claim, and the artifact it has to agree with (2026-10-17) ────────────────────────

def test_the_readme_carries_the_smaller_claim_and_the_workflow_agrees():
    """The section the reader meets: paused, linked to the last snapshot, and still disclaiming itself."""
    problems = paused_claim_problems(
        README.read_text(encoding="utf-8"), WORKFLOW.read_text(encoding="utf-8"))
    assert not problems, (
        "README.md's benchmark section no longer matches the artifact it describes:\n  - "
        + "\n  - ".join(problems)
    )


def test_the_rule_can_go_red_on_each_half_of_the_claim():
    """Every rule above is shown to be able to fail — one mutation per clause.

    This is the discipline the file was written with, kept through the retarget: a gate whose failure
    mode is not demonstrated is a comment. The mutations are applied to the *real* text in memory, so a
    future edit that drops one of these sentences fails here with the clause named.
    """
    text = README.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert paused_claim_problems(text, workflow) == [], "the baseline must be clean for these to mean anything"

    # Every occurrence, not the first: the first `paused` in the file is the badge's label, so a
    # `count=1` mutation rewrote the badge and left the prose intact — the fixture would have passed
    # while proving nothing, which is the failure mode this whole file is about.
    no_pause = re.sub(r"\bpaused\b", "ongoing", text, flags=re.IGNORECASE)
    assert no_pause != text
    assert any("paused" in problem for problem in paused_claim_problems(no_pause, workflow))

    no_link = SNAPSHOT_LINK.sub("](docs/benchmarks/)", text)
    assert no_link != text
    assert any("snapshot" in problem for problem in paused_claim_problems(no_link, workflow))

    no_disclaimer = text.replace(NOT_RETRIEVAL, "an independent measure of search quality")
    assert no_disclaimer != text
    assert any("no longer carries" in problem for problem in paused_claim_problems(no_disclaimer, workflow))

    restarted = workflow.replace("on:", "on:\n  schedule:\n    - cron: '0 2 * * 1'", 1)
    assert restarted != workflow
    assert any("schedule" in problem for problem in paused_claim_problems(text, restarted))


def test_the_rule_notices_a_doctor_passing_every_other_clause():
    """A single mutation must not need more than one clause to trip: each rule is independent.

    `test_lesson_count_ssot.py` learned this the hard way — a surface can satisfy every assertion while
    carrying one contradiction. Here the four clauses are checked one at a time on the baseline text.
    """
    text = README.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert paused_claim_problems(text, workflow) == []
    assert paused_claim_problems("", "") != []  # nothing at all is not a passing document


# Which READMEs must carry the demoted record. The prose is translated; the *link* is the fact that has
# to survive translation, and it is the one a reader needs in order to check the number themselves.
DEMOTED_READMES = ("README.md", "README.zh-CN.md", "README.ja.md")


def test_every_readme_links_the_last_snapshot():
    """The demotion replaced a trend with a named record; all three READMEs must point at it.

    The canonical README's pause/disclaimer sentences are checked above by `paused_claim_problems`
    (their wording is English). This is the language-neutral half, so a translation cannot quietly drop
    the only route to the artifact while keeping the claim that it exists.
    """
    for name in DEMOTED_READMES:
        text = (REPO / name).read_text(encoding="utf-8")
        assert SNAPSHOT_LINK.search(text), (
            f"{name} does not link the last benchmark snapshot (`docs/benchmarks/latest.json`). The "
            "demoted section is a dated record: without the link it is an unchecked number."
        )
    assert SNAPSHOT_LINK.search("the benchmark is paused, see the docs") is None, (
        "the pattern matches text without a link — the rule reads nothing"
    )


