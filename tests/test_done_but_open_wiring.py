#!/usr/bin/env python3
"""#2040's own advice was "不要新建工具" — the tool existed, and nothing called it.

`scripts/done_but_open.py` sat on `main`, tested, and referenced by no workflow. So the detector for
"the work is merged and the reporter was never told" was itself a rule that depended on somebody
remembering to run it — the exact failure it was written to end.

The issue's criteria about *what* it reports (the right intakes, with lesson path and age, and a list
that goes empty when the citation is removed) were already covered by `tests/test_done_but_open.py`
against the real corpus. The missing half was that it never ran, and that is what this file pins:
the scheduled caller, the one-pass/两形式 contract, and the two ways this automation could do harm —
firing every day with nothing in it, or closing somebody's issue because a filename matched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

WORKFLOW = REPO / ".github" / "workflows" / "intake-salvage-digest.yml"
SCRIPT = "scripts/done_but_open.py"


def _wf() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    return _wf()["jobs"]["salvage-digest"]["steps"]


def _wiring() -> str:
    """The `run:` block that invokes the detector — or a failure that says what is missing.

    Returning an empty string would let every assertion below pass against a deleted step, so the
    absence is raised here, once.
    """
    hits = [s for s in _steps() if SCRIPT in (s.get("run") or "")]
    assert len(hits) == 1, (
        f"expected exactly one workflow step to run {SCRIPT}; found {len(hits)} "
        "(#2040: the detector is only a mechanism if something calls it)"
    )
    return hits[0]["run"]


def _triggers() -> dict:
    """PyYAML reads the key `on:` as boolean `True` (YAML 1.1) — accept either spelling."""
    wf = _wf()
    return wf.get("on") or wf.get(True) or {}


# ── it runs at all ──────────────────────────────────────────────────────────────────
def test_a_scheduled_workflow_runs_the_detector():
    triggers = _triggers()
    assert "schedule" in triggers, "a detector nobody schedules is the state #2040 reported"
    assert any("cron" in str(t) for t in triggers["schedule"]), triggers["schedule"]


def test_it_runs_the_detector_exactly_once():
    """One API pass. Listing the whole open backlog twice per run is waste a reviewer should catch."""
    body = _wiring()
    assert body.count(SCRIPT) == 1, body


# ── the empty case must be silent, and decision must not read the prose ─────────────
def test_emptiness_is_decided_from_the_json_not_from_the_rendered_sentence():
    """`render([])` says 没有发现 in prose. Deciding "nothing to report" by string-matching that
    sentence breaks the day somebody rewords it — and breaks silently, in the direction of noise."""
    body = _wiring()
    assert "--json-out" in body, body
    assert "json.load" in body, body
    assert "没有发现" not in body, "the empty/full decision is being made from human-facing text"


def test_the_empty_case_stops_before_it_can_post_anything():
    """A report that fires every day with nothing in it is the alarm people mute."""
    body = _wiring()
    assert 'if [ "$count" = "0" ]' in body, body
    guard = body.index('if [ "$count" = "0" ]')
    first_post = body.find("gh issue")
    assert first_post > 0, body
    assert "exit 0" in body[guard:first_post], (
        "the empty branch must exit before any gh issue call, or a clean backlog posts noise"
    )


def test_a_clean_run_still_leaves_a_trace_that_it_ran():
    """'found nothing' and 'never ran' have to stay distinguishable (the #1920 lesson).

    Asserted on the empty branch specifically, not on the step: the step writes the summary again on
    the way out when it *does* find something, so a whole-step search passes with the clean path
    silenced — which the first version of this test did.
    """
    body = _wiring()
    guard = body.index('if [ "$count" = "0" ]')
    empty_branch = body[guard:body.index("exit 0", guard)]
    assert "GITHUB_STEP_SUMMARY" in empty_branch, (
        "the empty branch must record that it ran before exiting"
    )


# ── it must not do the maintainer's job for them ────────────────────────────────────
def test_it_never_closes_or_answers_the_intakes_it_finds():
    """SOP §3's receipt is a human sentence addressed to a reporter. A bot that closes an issue
    because a filename matched would be the worst possible version of this automation — and §2
    already says the noise bucket is not to be closed on our initiative."""
    body = _wiring()
    assert "gh issue close" not in body, body
    assert "--comment" not in body, (
        "it may comment on the digest issue, but must not comment on the intakes it reports"
    )


def test_the_report_lands_in_the_digest_the_audit_already_watches():
    """The new output rides the existing `salvage-digest` channel on purpose: `automation_output_audit`
    already fails a scheduled workflow that runs without producing anything, and a brand-new channel
    would have to be registered with it before that protection covered this step."""
    body = _wiring()
    assert "salvage-digest" in body, body
    from scripts.automation_output_audit import AUTOMATIONS

    assert any(a.workflow == WORKFLOW.name for a in AUTOMATIONS), (
        f"{WORKFLOW.name} produces output but is not registered with the audit"
    )


# ── the flag the wiring depends on ──────────────────────────────────────────────────
def test_json_out_gives_both_forms_from_one_call(tmp_path, capsys):
    """The workflow needs the human report for the issue body and a structural count for the branch."""
    from scripts.done_but_open import main

    target = tmp_path / "dbo.json"
    assert main(["--issue", "1472", "--json-out", str(target)]) == 0

    report = json.loads(target.read_text(encoding="utf-8"))
    assert [r["intake"] for r in report] == [1472], report

    printed = capsys.readouterr().out
    assert "#1472" in printed and "回执" in printed, printed


def test_json_out_is_not_written_when_nothing_is_found(tmp_path):
    """An empty list is still written as `[]` rather than left as a stale file from a previous run —
    otherwise a missing file and an empty report would be the same `if`."""
    from scripts.done_but_open import main

    target = tmp_path / "dbo.json"
    target.write_text('[{"intake": 1}]', encoding="utf-8")  # a previous run's answer
    assert main(["--issue", "999999999", "--json-out", str(target)]) == 0
    assert json.loads(target.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("flag", ["--json", "--json-out"])
def test_both_machine_readable_flags_survive_an_empty_report(flag, tmp_path, capsys):
    from scripts.done_but_open import main

    argv = ["--issue", "999999999", flag]
    if flag == "--json-out":
        argv.append(str(tmp_path / "o.json"))
    assert main(argv) == 0
    assert capsys.readouterr().out.strip(), "an empty report must still say something"
