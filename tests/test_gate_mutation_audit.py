#!/usr/bin/env python3
"""Tests for `scripts/gate_mutation_audit.py` — including the audit's *own* failure mode (#2045).

The audit exists because this repository found four gates in one day (2026-09-21) that looked like
gates and could never go red: a cross-platform matrix that ran zero tests on all 8 legs and printed
✅ (#2006/#2008), a tool-count badge that grepped the file it guarded (#1822), 23 of 26 tests in
#1999 passing with the production code reverted, and a test in #2002 asserting an environment
property that is true on the CI runner.

An audit that only ever reports ✅ would be exactly that defect again, one level up. So this file
tests both halves:

(a) it passes for the gates the repository actually covers, and the mutations really happen in a
    temp directory (`test_audit_passes_for_the_current_gates`);
(b) it **reports a failure** when pointed at a gate that cannot fail — a stub that ignores its
    input and always exits 0 (`test_audit_flags_a_gate_that_cannot_fail`,
    `test_cli_exits_non_zero_when_a_gate_cannot_fail`).

The stub scripts are what makes (b) a real test: without them the audit's "cannot go red" path
would only ever be exercised by the day it is needed.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import gate_mutation_audit as gma  # noqa: E402  (scripts/ is not a package)

# A gate that cannot fail: it ignores the artifact it is given and exits 0 whatever the input is.
ALWAYS_GREEN_GATE = "import sys\nprint('OK: everything looks fine')\nsys.exit(0)\n"
# The opposite stub, used to prove the audit also refuses to draw conclusions from a red baseline.
ALWAYS_RED_GATE = "import sys\nprint('FAIL: red no matter what')\nsys.exit(1)\n"


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _stub_gate(tmp_path: Path, body: str, *, name: str = "stub-always-green",
               apply=None) -> gma.Gate:
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
        command=lambda lesson, online: [sys.executable, str(script)],
        mutations=(gma.Mutation(name="break-it", description="break the artifact",
                                apply=apply or default_apply),),
    )


# ── the registry guards itself ────────────────────────────────────────
def test_the_audit_covers_the_gates_the_issue_names():
    """Acceptance: at least the lesson gate and the provenance gate, each with a real mutation."""
    assert {"lesson-gate", "provenance-gate"} <= set(gma.GATES)
    for name, gate in gma.GATES.items():
        assert gate.mutations, f"{name} has no mutation, so auditing it proves nothing"
        assert gate.script.is_file(), f"{name}: {gate.script} does not exist"
        for mutation in gate.mutations:
            assert mutation.description and mutation.apply


# ── (a) it passes for the gates we actually have ──────────────────────
def test_audit_passes_for_the_current_gates():
    """Every covered gate goes red under its (non-network) mutations, and nothing is touched."""
    watched = [REPO / gma.BASELINE_LESSON, gma.LESSON_GATE, gma.PROVENANCE_GATE]
    before = {path: _digest(path) for path in watched}

    report = gma.run_audit()

    assert report.ok, report.render()
    assert {result.gate.name for result in report.results} == set(gma.GATES), \
        "a shrunken registry must not make this test vacuous"

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
    assert observed >= 5, f"only {observed} offline mutations ran — the audit proved too little"

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


# ── (b) it flags a gate that cannot fail ──────────────────────────────
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
