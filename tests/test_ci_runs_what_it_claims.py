"""The CI gates must run the suite they name — and must be able to fail.

Three gates described themselves inaccurately, and all were found by an audit on
2026-10-02:

* ``node --test workers/*.test.mjs`` is a **top-level** glob. The repo has 66
  ``.test.mjs`` files; that glob reaches 65 of them. The one it misses,
  ``workers/email-register/email-utils.test.mjs``, tests the nested email worker
  that ``make deploy-email`` ships, and no workflow ran it.
* the pytest step passed both ``--cov=scripts`` and
  ``[tool.coverage.run] omit = ["scripts/*"]``; the omit wins (``*`` crosses
  ``/``), so ``scripts/`` contributed 0 lines and the printed TOTAL silently only
  described ``misakanet/``.
* the worker-suite step carried ``continue-on-error: true`` and no ``exit 1`` in
  the job read ``NODE_OUTCOME``: a red worker suite printed an ``::error`` and
  the required ``audit`` check still exited 0, so it could not block a merge —
  the one thing this workflow exists to do.

These tests are static by design -- they assert the invariant (the command's
scope is the whole tree / the measured package / a failure reaches the exit
code) that pyproject and the workflow have to agree on, without depending on a
node binary at pytest time.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PR_CHECKS = REPO_ROOT / ".github" / "workflows" / "pr-checks.yml"
MCP_STRESS = REPO_ROOT / ".github" / "workflows" / "mcp-stress.yml"

# The line that opens a job step in these workflows. Used to slice out a single
# step's YAML without a YAML parser (this file stays dependency-free on purpose).
STEP_START = re.compile(r"^\s*-\s+(?:name|uses):")


def _step_block(text: str, step_id: str) -> str:
    """The YAML text of the step whose ``id:`` is ``step_id``.

    From the ``- name:``/``- uses:`` that opens the step up to the one that opens
    the next step, so a key anywhere in the step can be asserted on without
    matching the key in a neighbouring step.
    """
    lines = text.splitlines()
    anchor = next((i for i, line in enumerate(lines) if line.strip() == f"id: {step_id}"), None)
    assert anchor is not None, f"pr-checks.yml has no step with `id: {step_id}`"
    starts = [i for i, line in enumerate(lines) if STEP_START.match(line)]
    begin = max(i for i in starts if i <= anchor)
    end = min((i for i in starts if i > anchor), default=len(lines))
    return "\n".join(lines[begin:end])


def _node_suite_commands(workflow: Path) -> list[str]:
    """Every `node --test <targets>` invocation in a workflow, target part only."""
    text = workflow.read_text(encoding="utf-8")
    return [
        line.strip().split("node --test", 1)[1].strip()
        for line in text.splitlines()
        if "node --test" in line and not line.strip().startswith("#")
    ]


def test_the_audit_worker_suite_covers_nested_test_files():
    """`audit` is the required check, so its worker suite must be the whole tree."""
    commands = _node_suite_commands(PR_CHECKS)
    assert commands, "pr-checks.yml no longer runs a node test suite"
    suite = [c for c in commands if "workers/" in c]
    assert suite, f"no worker suite in pr-checks.yml; found {commands}"
    target = suite[0]
    assert target.startswith("'") or target.startswith('"'), (
        "the worker glob must be quoted: unquoted, the shell expands `workers/**/*.test.mjs` "
        f"to the nested files only, which is a different suite (got {target!r})"
    )
    assert "**" in target, (
        f"a top-level glob cannot reach workers/email-register/email-utils.test.mjs (got {target!r})"
    )


def test_the_stress_worker_suite_covers_nested_test_files():
    """The other workflow that runs the suite must not silently stay narrower."""
    commands = _node_suite_commands(MCP_STRESS)
    suite = [c for c in commands if "workers/" in c and "*" in c]
    assert suite, f"no globbed worker suite in mcp-stress.yml; found {commands}"
    target = suite[0]
    assert "**" in target and (target.startswith("'") or target.startswith('"')), (
        f"mcp-stress.yml's worker suite must be the quoted recursive glob (got {target!r})"
    )


def test_the_quoted_glob_reaches_every_test_file_in_the_tree():
    """The pattern the workflows use resolves to *every* .test.mjs, nested included.

    This is the executable half of the claim: `Path.glob("**/*.test.mjs")` is the
    same "zero or more directories" semantics node's test runner uses for a quoted
    `**` target.
    """
    all_tests = sorted(p.relative_to(REPO_ROOT).as_posix() for p in REPO_ROOT.glob("**/*.test.mjs"))
    top_level = sorted(
        p.relative_to(REPO_ROOT).as_posix() for p in REPO_ROOT.glob("workers/*.test.mjs")
    )
    recursive = sorted(
        p.relative_to(REPO_ROOT).as_posix() for p in REPO_ROOT.glob("workers/**/*.test.mjs")
    )
    assert recursive == sorted(t for t in all_tests if t.startswith("workers/")), (
        "the recursive glob does not reach every worker test file"
    )
    # The measurement behind this file (66 files, 65 of them top-level, measured 2026-10-02) is history
    # and belongs in the comment above rather than in an assertion: pinning the *count* would turn this
    # into a test that fails when someone adds a worker test, which is the opposite of what it is for.
    # What has to stay true is that a nested file exists at all — that is what makes the quoting
    # load-bearing — and that the one the old glob missed is still covered.
    missed = set(recursive) - set(top_level)
    assert missed, (
        "no nested worker test file is left: the quoted `**` glob is no longer load-bearing, so this "
        "test can no longer tell it apart from the unquoted top-level form it replaced"
    )
    assert "workers/email-register/email-utils.test.mjs" in recursive, (
        "the nested email-worker suite — the file the old top-level glob skipped — is not reached"
    )


def test_the_node_suite_step_does_not_swallow_its_own_failure():
    """`continue-on-error` on the node step gives the job a green conclusion.

    Measured on ``main`` before this test existed: the step carried it, so a red
    worker suite was reported as a successful step, the verdict block only turned
    that into an annotation, and `audit` (the required check) exited 0.
    """
    block = _step_block(PR_CHECKS.read_text(encoding="utf-8"), "node_tests")
    assert block, "the `Run Worker Test Suite (node)` step is gone from pr-checks.yml"
    assert not re.search(r"^\s*continue-on-error:", block, re.MULTILINE), (
        "the `Run Worker Test Suite (node)` step must not carry `continue-on-error`: it reports the "
        "step as successful, which is what let a red worker suite show up as a green `audit` check"
    )
    assert re.search(r"if:\s*steps\.scope\.outputs\.scope == 'full'", block), (
        "the node suite runs only in `full` scope, and the exit-code guard is written against that "
        "scope; if the condition moves, the guard has to move with it"
    )


def test_the_audit_exit_code_reads_the_node_outcome():
    """`VERDICT_PASS=false` only annotates; an `exit 1` is what fails the run.

    Same shape as the pytest guard right above it: the `exit 1` sits under
    ``[ "$SCOPE" = "full" ]`` and the node outcome, so `lessons-only` / `ci-only`
    / `js-deps-only` PRs — which never run the suite — cannot be failed by it.
    """
    text = PR_CHECKS.read_text(encoding="utf-8")
    marker = "# ── Exit with failure if any hard gate fails ──"
    assert marker in text, (
        "the exit-code section marker is gone from pr-checks.yml; this test can no longer find the "
        "one place a hard gate turns into a non-zero exit"
    )
    exit_section = text.split(marker, 1)[1]
    lines = exit_section.splitlines()
    guard_at = next(
        (
            i
            for i, line in enumerate(lines)
            if re.search(r'if \[ "\$SCOPE" = "full" \][^\n]*NODE_OUTCOME[^\n]*!= "success"', line)
        ),
        None,
    )
    assert guard_at is not None, (
        "the exit-code section has no `exit 1` guard reading `NODE_OUTCOME` under the `full` scope: "
        "a failing worker suite would print an `::error` and the required `audit` check would still "
        "exit 0"
    )
    # The guard's body, not the whole section: `exit 1` has to be *inside* it.
    window = "\n".join(lines[guard_at : guard_at + 12])
    assert "exit 1" in window, (
        "the guard that reads `NODE_OUTCOME` does not `exit 1` — the verdict is still annotation-only"
    )


def test_coverage_flag_names_the_package_it_measures():
    """No `--cov=scripts`: it is omitted, so the flag only ever printed a wrong TOTAL."""
    text = PR_CHECKS.read_text(encoding="utf-8")
    cov_lines = [ln for ln in text.splitlines() if "--cov=" in ln and not ln.strip().startswith("#")]
    assert cov_lines, "pr-checks.yml no longer runs pytest with coverage"
    for line in cov_lines:
        assert "--cov=scripts" not in line, (
            "the coverage run must not pass --cov=scripts: [tool.coverage.run] omit excludes "
            f"scripts/ anyway, so the flag misdescribes the TOTAL (line: {line.strip()!r})"
        )
        assert "--cov=misakanet" in line, f"coverage must measure misakanet/ (line: {line.strip()!r})"
        assert "--cov-fail-under=20" in line, (
            "the coverage floor is a separate decision -- this task deliberately did not move it "
            f"(line: {line.strip()!r})"
        )


def test_pyproject_documents_the_scripts_coverage_debt():
    """`scripts/` being unmeasured is accepted debt, and the debt must say so."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("[tool.coverage.run]", 1)[1].split("[tool.mypy]", 1)[0]
    assert 'omit = ["scripts/*"]' in block, "the scripts/ omit was removed from pyproject.toml"
    assert re.search(r"technical debt|accepted debt|accepted technical debt", block, re.IGNORECASE), (
        "pyproject.toml must record scripts/ being outside the measured set as accepted debt"
    )
    gates = (REPO_ROOT / "docs" / "ci-gates.md").read_text(encoding="utf-8")
    assert "misakanet" in gates and "technical debt" in gates.lower(), (
        "docs/ci-gates.md must record that coverage measures misakanet/ only, as accepted debt"
    )
