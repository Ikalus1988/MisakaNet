#!/usr/bin/env python3
"""Tests for `scripts/gate_mutation_audit.py` — including the audit's *own* failure mode (#2045).

The audit exists because this repository found four gates in one day (2026-09-21) that looked like
gates and could never go red: a cross-platform matrix that ran zero tests on all 8 legs and printed
✅ (#2006/#2008), a tool-count badge that grepped the file it guarded (#1822), 23 of 26 tests in
#1999 passing with the production code reverted, and a test in #2002 asserting an environment
property that is true on the CI runner.

An audit that only ever reports ✅ would be exactly that defect again, one level up. So this file
tests three things:

(a) the registry follows `docs/ci-gates.md` — the hard gates are parsed from the table, every one
    of them has a gate that names it, and a hard gate nobody proves is reported as an audit failure
    (#3837). The four contexts the issue names are asserted, so a parser that read the wrong table
    cannot pass by agreeing with itself;
(b) it passes for the gates the repository actually covers, and the mutations really happen in a
    temp directory (`test_audit_passes_for_the_current_gates`);
(c) it **reports a failure** when pointed at a gate that cannot fail — a stub that ignores its
    input and always exits 0 (`test_audit_flags_a_gate_that_cannot_fail`,
    `test_cli_exits_non_zero_when_a_gate_cannot_fail`).

The stub scripts are what makes (c) a real test: without them the audit's "cannot go red" path
would only ever be exercised by the day it is needed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import check_documented_gates as ratchet  # noqa: E402  (scripts/ is not a package)
import gate_mutation_audit as gma  # noqa: E402

# The required contexts the ruleset read back on 2026-09-29 (#3837). `docs/ci-gates.md` is the
# source of the list — this literal is the acceptance oracle, not a second copy the registry may
# follow: if the ruleset changes, the table changes, `hard_gates()` follows it, and this list is
# updated in the same pull request.
EXPECTED_HARD_GATES = {
    "DCO / Signed-off-by",
    "test (ubuntu-latest, 3.11)",
    "test (windows-latest, 3.11)",
    "gate",
    "audit",
}

# A gate that cannot fail: it ignores the artifact it is given and exits 0 whatever the input is.
ALWAYS_GREEN_GATE = "import sys\nprint('OK: everything looks fine')\nsys.exit(0)\n"
# The opposite stub, used to prove the audit also refuses to draw conclusions from a red baseline.
ALWAYS_RED_GATE = "import sys\nprint('FAIL: red no matter what')\nsys.exit(1)\n"


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _stub_gate(tmp_path: Path, body: str, *, name: str = "stub-always-green",
               apply=None, command=None) -> gma.Gate:
    """A gate whose script is a stub, with one mutation that edits the artifact."""
    script = tmp_path / f"{name}.py"
    script.write_text(body, encoding="utf-8")

    def prepare(run_dir: Path) -> Path:
        artifact = run_dir / "lessons" / "contrib" / "stub.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("---\ntitle: stub\n---\n\n## Problem\n\nstub\n", encoding="utf-8")
        return artifact

    def default_apply(artifact: Path) -> None:
        artifact.write_text(artifact.read_text(encoding="utf-8") + "\nbroken\n", encoding="utf-8")

    return gma.Gate(
        name=name,
        description="a stub gate (test fixture)",
        script=script,
        prepare=prepare,
        command=command or (lambda artifact, online: [sys.executable, str(script), str(artifact)]),
        mutations=(gma.Mutation(name="break-it", description="break the artifact",
                                apply=apply or default_apply),),
    )


# ── the registry follows the documented hard gates (#3837) ───────────
def test_hard_gates_are_read_from_the_documented_table():
    """The list has one source: the table, not a constant in this script or in this test."""
    assert set(gma.hard_gates()) == EXPECTED_HARD_GATES
    # Two independent readers of the same table must agree — `hard_gates()` and the ratchet that
    # compares it with the live ruleset (`scripts/check_documented_gates.py`). If this one reads the
    # advisory tables by accident, it disagrees here instead of silently passing.
    assert set(gma.hard_gates()) == set(ratchet.parse_documented(ratchet.DOC))


def test_every_hard_gate_has_a_gate_that_proves_it():
    """Coverage, not a subset: every required context is named by a `Gate`, and vice versa."""
    covered = {context for gate in gma.GATES.values()
               for context in ((gate.check,) if gate.check else ()) + tuple(gate.also_checks)}
    assert covered == EXPECTED_HARD_GATES, (
        f"the audit proves {sorted(covered)} but the ruleset requires {sorted(EXPECTED_HARD_GATES)}")
    assert gma.missing_hard_gates() == ()
    for name, gate in gma.GATES.items():
        assert gate.mutations, f"{name} has no mutation, so auditing it proves nothing"
        assert gate.script.is_file(), f"{name}: {gate.script} does not exist"
        for mutation in gate.mutations:
            assert mutation.description and mutation.apply
        if gate.check is None:
            assert gate.why, (
                f"{name} is not a hard gate and does not say why it is in the audit anyway — an "
                f"entry nobody asked to prove is just a slow check")
        else:
            assert gate.check in EXPECTED_HARD_GATES, (
                f"{name} claims the context {gate.check!r}, which docs/ci-gates.md does not list")


def test_the_provenance_gate_is_kept_and_explains_its_position():
    """It is not a hard gate (#3837), and it is not in the list by accident either."""
    gate = gma.GATES["provenance-gate"]
    assert gate.check is None
    assert "not a required context" in gate.why
    assert "cannot block a merge" in gate.why
    assert gate.mutations, "the provenance gate's mutations are the reason it is worth keeping"


def test_a_hard_gate_without_a_mutation_fails_the_audit():
    """The interesting half: the registry shrinking must not make the audit vacuously green."""
    reduced = [gate for gate in gma.GATES.values() if gate.check != "audit"]
    assert gma.missing_hard_gates(reduced) == ("audit",)

    # A report that proves one gate but claims the full hard-gate set is not a pass.
    proven = gma.GateResult(gate=gma.GATES["lesson-gate"], control_ok=True)
    report = gma.AuditReport([proven], hard_gates=tuple(gma.hard_gates()))
    assert not report.ok
    failure = report.failures[0]
    assert "'audit'" in failure and "no mutation" in failure
    assert "docs/ci-gates.md" in failure
    assert "FAILED" in report.render()

    # A `--gate` subset makes no claim about coverage, so it is not failed for what it did not run.
    subset = gma.AuditReport([proven], hard_gates=None)
    assert subset.uncovered == ()
    assert subset.ok


def test_an_unreadable_hard_gate_list_is_a_hard_error(tmp_path):
    """A document whose table cannot be read must not read as "every gate is covered"."""
    with pytest.raises(gma.AuditError, match="single source"):
        gma.hard_gates(tmp_path / "no-such-document.md")

    renamed = tmp_path / "ci-gates.md"
    renamed_text = ratchet.DOC.read_text(encoding="utf-8").replace(
        "## Hard Gates (must pass)", "## Hard Gates (required)")
    renamed.write_text(renamed_text, encoding="utf-8")
    with pytest.raises(gma.AuditError, match="exactly once"):
        gma.hard_gates(renamed)


def test_list_gates_names_the_contexts_and_exits_zero(capsys):
    """A maintainer asking "what is covered" gets the mapping, not a list to compare by eye."""
    assert gma.main(["--list-gates"]) == 0
    out = capsys.readouterr().out
    for context in EXPECTED_HARD_GATES:
        assert context in out, f"--list-gates does not name {context!r}"
    for name in gma.GATES:
        assert name in out, f"--list-gates does not name the gate {name!r}"
    assert "not a hard gate" in out, "provenance-gate's position must be visible here too"


# ── (b) it passes for the gates we actually have ──────────────────────
# The planted token: the shape leaves this source, the payload does not.
#
# The third-party scanner reads whole files, so writing a quoted value assigned to a token-shaped
# name in *this* source reports the repository against itself — alerts #381/#382, opened
# 2026-10-25, on a file whose value is fake and only ever lands in a throwaway scenario. The
# planted file has to keep carrying the shape: the audit's red path depends on it.
def test_the_planted_token_is_assembled_at_run_time_and_the_plant_still_carries_it(tmp_path):
    scenario = tmp_path / "scenario"
    gma._mutate_audit_hardcoded_token(scenario)
    planted = (scenario / "workers" / "leaky.mjs").read_text(encoding="utf-8")
    assert 'token: "' in planted, planted
    assert gma._fake_github_token() in planted, planted

    source = (REPO / "scripts" / "gate_mutation_audit.py").read_text(encoding="utf-8")
    assert not re.search(r"token\s*[=:]\s*[\"'][^\s\"']{8,}", source), (
        "this source must not carry the shape the scanner reads — the planted line is assembled "
        "at run time instead, so the repository is not reported against itself")


def test_audit_passes_for_the_current_gates():
    """Every covered gate goes red under its (non-network) mutations, and nothing is touched."""
    if gma._find_bash() is None:
        # The workflow-driven gates execute their step bodies with bash. The required ubuntu leg
        # always has it; a developer machine without bash cannot prove those gates, and saying so is
        # better than reporting a red gate that is really a missing shell.
        pytest.skip("bash is required to execute the workflow-driven gates on this machine")
    watched = [
        REPO / gma.BASELINE_LESSON, gma.LESSON_GATE, gma.PROVENANCE_GATE,
        gma.HARD_GATES_DOC, gma.DCO_ACTION, gma.DCO_WORKFLOW,
        gma.CROSS_PLATFORM_WORKFLOW, gma.PR_CHECKS_WORKFLOW,
    ]
    before = {path: _digest(path) for path in watched}

    report = gma.run_audit()

    assert report.ok, report.render()
    assert {result.gate.name for result in report.results} == set(gma.GATES), \
        "a shrunken registry must not make this test vacuous"
    assert report.uncovered == (), (
        "a hard gate in docs/ci-gates.md has no mutation: " + ", ".join(report.uncovered))

    observed = 0
    for result in report.results:
        # The control run is what makes a red mutation meaningful: the artifact is valid before it
        # is broken, so the red can only come from the mutation.
        assert result.control_ok, f"{result.gate.name}: baseline artifact is not green\n" + report.render()
        for mutation_run in result.mutations:
            if mutation_run.mutation.network:
                assert mutation_run.outcome == gma.OUTCOME_SKIPPED
                continue
            observed += 1
            assert mutation_run.outcome == gma.OUTCOME_RED, (
                f"{result.gate.name}/{mutation_run.mutation.name} did not go red "
                f"({mutation_run.outcome}):\n{mutation_run.output}\n" + report.render())
    assert observed >= 15, f"only {observed} offline mutations ran — the audit proved too little"

    # "The mutations happen in a temporary copy, never in the repository tree" — asserted, not
    # promised. The audit hashes nothing itself; this is the test's own check on it.
    after = {path: _digest(path) for path in watched}
    assert after == before, "the audit modified the repository: " + ", ".join(
        str(path) for path in watched if after[path] != before[path])


def test_network_mutations_are_skipped_offline_without_failing_the_audit():
    """A mutation that needs the network is skipped, never silently counted as a pass."""
    declared = [m for gate in gma.GATES.values() for m in gate.mutations if m.network]
    assert declared, "no network mutation is declared any more — update this test with it"

    report = gma.run_audit([gma.GATES["provenance-gate"]])

    assert report.ok, report.render()
    skipped = [m for result in report.results for m in result.mutations
               if m.outcome == gma.OUTCOME_SKIPPED]
    assert skipped, "the network mutation was not reported as skipped"
    assert all(m.mutation.network for m in skipped)
    assert "needs the network" in report.render()


# ── (c) it flags a gate that cannot fail ──────────────────────────────
def test_audit_flags_a_gate_that_cannot_fail(tmp_path):
    """A gate that always exits 0 must be reported as an audit FAILURE, by name."""
    gate = _stub_gate(tmp_path, ALWAYS_GREEN_GATE)
    report = gma.run_audit([gate])

    assert not report.ok, "a gate that cannot go red was reported as a pass:\n" + report.render()
    failures = report.failures
    assert len(failures) == 1, failures
    assert "cannot fail" in failures[0], failures
    assert gate.name in failures[0]
    assert f"mutation 'break-it'" in failures[0]

    rendered = report.render()
    assert gate.name in rendered
    assert "GREEN ❌" in rendered
    assert "mutation audit: FAILED" in rendered


def test_cli_exits_non_zero_when_a_gate_cannot_fail(tmp_path, monkeypatch, capsys):
    """The same failure, through the entry point CI actually calls (`sys.exit(main())`)."""
    gate = _stub_gate(tmp_path, ALWAYS_GREEN_GATE, name="stub-always-green")
    monkeypatch.setitem(gma.GATES, gate.name, gate)

    assert gma.main(["--gate", gate.name]) == 1

    out = capsys.readouterr().out
    assert "cannot fail" in out
    assert gate.name in out
    assert "mutation audit: FAILED" in out
    # Only the stub ran: `--gate` must scope the audit instead of silently running everything.
    assert "1 gate(s), 1 mutation(s)" in out


def test_cli_exits_two_for_an_unknown_gate(capsys):
    """Auditing nothing while exiting 0 would be the same defect, in the audit's own CLI."""
    assert gma.main(["--gate", "no-such-gate"]) == 2
    err = capsys.readouterr().err
    assert "no-such-gate" in err
    assert "nothing was audited" in err
    assert "lesson-gate" in err, "the error must list the gates that do exist"


# ── the other ways a mutation run can prove nothing ──────────────────
def test_a_red_baseline_is_reported_as_a_control_failure(tmp_path):
    """If the unmutated artifact already fails, a red mutation proves nothing — say so."""
    gate = _stub_gate(tmp_path, ALWAYS_RED_GATE, name="stub-always-red")
    report = gma.run_audit([gate])

    assert not report.ok
    assert "baseline artifact is already failing" in report.render()
    assert any("RED on the unmutated baseline" in failure for failure in report.failures)


def test_a_mutation_that_does_not_apply_is_reported(tmp_path):
    """A no-op mutation would be reported as "the gate cannot fail" — a false accusation."""
    gate = _stub_gate(tmp_path, ALWAYS_GREEN_GATE, name="stub-noop-mutation",
                      apply=lambda artifact: None)
    report = gma.run_audit([gate])

    outcomes = [m.outcome for result in report.results for m in result.mutations]
    assert outcomes == [gma.OUTCOME_NOT_APPLIED], report.render()
    assert not report.ok
    assert "did not apply" in report.render()
    assert "cannot fail" not in "\n".join(report.failures)


def test_a_mutation_that_leaves_the_artifact_byte_identical_is_reported(tmp_path):
    """Rewriting a file with its own contents is still a no-op, and must not read as a pass."""
    gate = _stub_gate(
        tmp_path, ALWAYS_GREEN_GATE, name="stub-rewrite-mutation",
        apply=lambda artifact: artifact.write_text(artifact.read_text(encoding="utf-8"),
                                                   encoding="utf-8"))
    report = gma.run_audit([gate])

    outcomes = [m.outcome for result in report.results for m in result.mutations]
    assert outcomes == [gma.OUTCOME_NOT_APPLIED], report.render()
    assert "byte-identical" in report.render()


def test_auditing_no_gate_at_all_is_not_a_pass():
    """#2006/#2008 ran zero tests on all 8 legs and printed ✅ — the audit must not repeat it."""
    report = gma.run_audit([])

    assert not report.ok
    assert "no gate was audited" in report.failures[0]
    assert "mutation audit: FAILED" in report.render()


def test_a_missing_gate_script_is_an_audit_failure(tmp_path):
    """A gate that is not there cannot be audited — never silently skipped."""
    gate = _stub_gate(tmp_path, ALWAYS_GREEN_GATE, name="stub-missing-script")
    gate = gma.Gate(name=gate.name, description=gate.description,
                    script=tmp_path / "gone.py", prepare=gate.prepare,
                    command=gate.command, mutations=gate.mutations)
    report = gma.run_audit([gate])

    assert not report.ok
    assert "gate script not found" in report.render()


# ── the workflow-driven gates: a moved criterion is not a red gate ───
def test_a_criterion_that_cannot_be_evaluated_is_not_counted_as_red(tmp_path):
    """Exit 3 means "could not judge" — the third outcome, and the one that must never read as a
    pass. A renamed step or a missing input would otherwise credit the gate for an accident."""
    stub = (
        "import sys\n"
        "from pathlib import Path\n"
        "text = Path(sys.argv[1]).read_text(encoding='utf-8')\n"
        "print('CANNOT JUDGE: the step moved')\n"
        "sys.exit(3 if 'broken' in text else 0)\n"
    )
    gate = _stub_gate(tmp_path, stub, name="stub-cannot-judge")
    report = gma.run_audit([gate])

    outcomes = [m.outcome for result in report.results for m in result.mutations]
    assert outcomes == [gma.OUTCOME_ERROR], report.render()
    assert "could not be evaluated (exit 3)" in report.render()
    assert "cannot fail" not in "\n".join(report.failures), (
        "a criterion that could not be evaluated must not be accused of being unable to fail")


def test_a_moved_workflow_step_says_where_the_criterion_went():
    """The extraction is strict: a step that no longer exists is an error, not an empty script."""
    with pytest.raises(gma.CriterionUnavailable, match="no step named"):
        gma._workflow_step_body(gma.PR_CHECKS_WORKFLOW, "audit", "No Such Step Any More")
    with pytest.raises(gma.CriterionUnavailable, match="no job"):
        gma._workflow_step_body(gma.PR_CHECKS_WORKFLOW, "no-such-job", "Secret Scan")
    with pytest.raises(gma.CriterionUnavailable, match="no value"):
        gma._render("echo ${{ steps.gone.outputs.value }}", {},
                    where="test")


def test_the_pytest_legs_verdict_is_the_workflow_step_itself():
    """The mutation executes `Verify test outcome`; if that arm disappears the audit follows it.

    This pins the two facts the mutation relies on, so a rewrite of the leg's verdict is a red test
    rather than a silently weaker audit: exit 5 (nothing collected) and exit 2 (collection error)
    both have their own `exit 1`.
    """
    body = gma._workflow_step_body(gma.CROSS_PLATFORM_WORKFLOW, "test", "Verify test outcome")
    assert "5)" in body and "No tests were collected at all" in body
    assert "2)" in body and "The suite was interrupted" in body
    assert body.count("exit 1") >= 4


def test_the_node_summary_is_read_in_both_reporter_shapes():
    """Node's reporter changed the summary prefix; the audit must judge the run, not the spelling.

    Node v23.0.0 switched the default reporter on a non-TTY stdout from `tap` to `spec`, and the
    summary lines changed their prefix from `#` to `ℹ` (U+2139). The audit job pins node 22, so
    the audit itself reads the TAP shape — but this script also runs on whatever node the runner
    image ships, because `ci-cross-platform.yml` has no setup-node step and the macOS image is on
    node 24. Measured 2026-10-26: the macOS legs ended with `ℹ fail 0`, the criterion came back
    "could not be evaluated" (exit 3), and the matrix went red on a gate that was perfectly fine.

    So both shapes have to be read — and a summary of zero tests has to stay unreadable in both:
    that is the #2006 shape this check exists for.
    """
    for prefix in ("#", "ℹ"):
        green = f"{prefix} tests 3\n{prefix} pass 3\n{prefix} fail 0\n"
        red = f"{prefix} tests 3\n{prefix} pass 2\n{prefix} fail 1\n"
        assert gma.NODE_PASS_RE.search(green), prefix
        assert gma.NODE_FAIL_RE.search(red), prefix
        # A run that collected nothing is not a run that passed: `pass 0` proves nothing either way.
        assert not gma.NODE_PASS_RE.search(f"{prefix} pass 0\n"), prefix
        assert not gma.NODE_FAIL_RE.search(green), prefix


def test_the_coverage_floor_uses_the_real_plugin_when_it_is_installed():
    """The one criterion-level stub says which mode it ran in, and CI must not silently stub it.

    `audit-coverage-floor` is the only mutation whose criterion is *modelled* when `pytest-cov` is
    absent (a developer machine); the CI job installs the plugin, so the real floor runs there. If
    that ever stops happening, this test says so on the run that has the plugin instead of leaving
    a modelled comparison in the proof.
    """
    report = gma.run_audit([gma.GATES["audit-coverage-floor"]])
    assert report.ok, report.render()
    rendered = report.render()
    if importlib.util.find_spec("pytest_cov") is not None:
        # pytest-cov has two versions of its verdict in the wild: the summary line ("Required test
        # coverage of … not reached") and the error line ("ERROR: Coverage failure: …"). The report
        # quotes the first error line, so accept either plugin wording — but never the model's
        # "modelled comparison" line, which is what the real-vs-stub distinction is about.
        assert "Required test coverage of" in rendered or "Coverage failure" in rendered, (
            "pytest-cov is installed, so the mutation must use the real floor, not the model:\n"
            + rendered)
    else:
        assert "modelled comparison" in rendered, (
            "the fallback must say that it is modelled, not present itself as the plugin:\n"
            + rendered)
