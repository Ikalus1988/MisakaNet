#!/usr/bin/env python3
"""Gate mutation audit — can the gates still go *red*? (issue #2045)

On 2026-09-21 this repository found four gates that looked like gates and could never fail:

* the cross-platform matrix ran **zero tests on all 8 legs** and printed ✅ (#2006/#2008);
* a tool-count badge grepped **the very file it guarded** (#1822);
* **23 of 26 tests** in #1999 passed with the production code reverted;
* a test in #2002 asserted an environment property (`PATH=/usr/bin:/bin`) that is true on the
  CI runner, so it could not fail.

That is a structural failure mode, not four accidents: a check that cannot fail is worse than
no check, because it reports success on broken input and retires the suspicion that would have
found the bug. The fix pattern this repository has adopted is to **prove a gate can fail,
deliberately, and make the proof part of the repository** instead of a habit.

What this script does
---------------------
For every gate in `GATES` it builds a *valid* artifact in a temporary directory (never the
repository tree) — a lesson, a git history, a pytest project, a tree with a planted secret — asserts
the gate is green on it, then applies each **mutation** — a deliberate break of the thing the gate
is supposed to check — and asserts the gate exits non-zero.

The suspicious outcome is a **green** gate. If a gate stays green under its mutation, this script
prints `cannot fail` and exits non-zero; the same is true for a mutation that did not apply, a
baseline artifact that is already red, and a gate that hangs. "The gate went red" is the only
outcome counted as success.

The hard gates are the ones the branch ruleset requires (#3837)
---------------------------------------------------------------
`docs/ci-gates.md`'s *Hard Gates (must pass)* table is the single source: `hard_gates()` parses it
on every run, every `Gate` names the required-status-check context it proves in `Gate.check`, and a
full run **fails** when a context in that table has no mutation in `GATES`. Nothing here restates
the list, so the table and the registry cannot drift apart; changing the table without adding the
mutation turns this audit red (and `tests/test_gate_mutation_audit.py` with it).

Three of those contexts are not computed by a standalone script — `DCO / Signed-off-by` is an
inline `actions/github-script` step plus a composite action, `test (ubuntu-latest, 3.11)` is a
shell step that maps pytest's exit code to a verdict, and `audit` is a shell job whose `exit 1`
arms are the verdict. GitHub Actions does not run locally, so the mutations for those gates execute
the **workflow step bodies themselves**, read out of the YAML with `yaml.safe_load` and rendered
with their `${{ … }}` inputs supplied. A pull request that deletes the `5) … exit 1` arm of the
pytest leg, or the `Signed-off-by:` grep in the DCO action, therefore makes this audit go *green* —
which is the finding it exists to produce. These are mutations of the gate's **criterion**, never of
product code: the scenario is a throwaway directory and the repository is not edited.

One criterion is modelled rather than delegated: the `audit` job's coverage floor
(`pytest --cov-fail-under=…`). The number is read from `pr-checks.yml`, and the comparison is
evaluated here because `pytest-cov` is not installed on every machine that runs this (the CI job
does install it, and then the real plugin runs the real floor). The mutation is still named for
what it breaks — the floor's ability to reject a falling coverage number — and the mode is printed.

Usage
-----
    python3 scripts/gate_mutation_audit.py                 # offline, every covered gate
    python3 scripts/gate_mutation_audit.py --gate lesson-gate
    python3 scripts/gate_mutation_audit.py --list-gates    # what is covered, and which hard gate
    python3 scripts/gate_mutation_audit.py --online        # also mutations that need the network
    python3 scripts/gate_mutation_audit.py -v              # full output of every gate run

Exit codes
----------
    0   every hard gate is covered, and every covered gate went red under every mutation that ran
    1   audit failed: a gate stayed green, a hard gate has no mutation, or a truth could not be
        judged (the interesting outcome)
    2   the audit could not run at all (unknown --gate, missing gate script/document, no PyYAML)

How to add a gate or a mutation, and who acts on a red result: `docs/maintainer/gate-mutation-audit.md`.
It runs on **every pull request**, weekly on a schedule, and by manual dispatch
(`.github/workflows/gate-mutation-audit.yml`). The pull request trigger is the point of #3837: a
change that quietly removes a gate's teeth is exactly the change a periodic sweep finds a week too
late, and the run is one job of a few minutes rather than a matrix.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

REPO = Path(__file__).resolve().parent.parent
# This file, used as the entry point for the workflow-driven gates: `--_drive <spec> <scenario>`
# executes the gate's own verdict and exits 0 (green) or non-zero (red), so the parent process sees
# a real gate run rather than an in-process function call that could be mistaken for one.
SELF = Path(__file__).resolve()

LESSON_GATE = REPO / "scripts" / "lesson_gate.py"
PROVENANCE_GATE = REPO / "scripts" / "check_provenance.py"

# Where each hard gate's verdict is actually computed. `docs/ci-gates.md` names the context; these
# are the artifacts that carry the criterion, and every one of them is executed (see `_drive`).
HARD_GATES_DOC = REPO / "docs" / "ci-gates.md"
DCO_ACTION = REPO / ".github" / "actions" / "dco-audit" / "action.yml"
DCO_WORKFLOW = REPO / ".github" / "workflows" / "dco-check.yml"
CROSS_PLATFORM_WORKFLOW = REPO / ".github" / "workflows" / "ci-cross-platform.yml"
PR_CHECKS_WORKFLOW = REPO / ".github" / "workflows" / "pr-checks.yml"

DEFAULT_TIMEOUT = 120.0
# Reserved exit status for "the criterion could not be evaluated": a step was renamed, an input had
# no value, a scanner crashed. It must not be read as a verdict — a broken gate is not a gate that
# can fail — so the runner reports it as ERROR. None of the covered gates returns 3 for a real
# finding (lesson_gate/check_provenance/check_worker_secrets return 0 or 1; the pytest leg's verdict
# is 0 or 1), which is what makes the value safe to reserve.
EXIT_CANNOT_JUDGE = 3


def hard_gates(path: Path | None = None) -> tuple[str, ...]:
    """The required status-check contexts, read from `docs/ci-gates.md` (#3837).

    This is the **only** statement of the set: `GATES` names a context per entry and `run_audit`
    compares the two, so adding a hard gate to the document without proving it can fail turns the
    audit red instead of leaving a gate nobody has tested. Only the *Hard Gates* section is read,
    and only until the next `## ` heading — the advisory tables below it look identical (the same
    rule, for the same reason, as `scripts/check_documented_gates.py`).
    """
    document = path or HARD_GATES_DOC
    if not document.is_file():
        raise AuditError(f"{document} is missing — it is the single source of the hard-gate list")
    text = document.read_text(encoding="utf-8")
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines)
              if line.rstrip() == "## Hard Gates (must pass)"]
    if len(starts) != 1:
        raise AuditError(
            f"{document} must contain the heading '## Hard Gates (must pass)' exactly once "
            f"(found {len(starts)}) — the audit reads its table as the authoritative set")
    contexts: list[str] = []
    for line in lines[starts[0] + 1:]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        name = cells[0].strip("*`_ ").strip()
        # The header row ("Check (context as GitHub reports it)") and the |---| separator are not
        # contexts. Mirrors `parse_documented()` in scripts/check_documented_gates.py, which reads
        # the same table for the same purpose.
        if not name or set(name) <= {"-", ":", " "}:
            continue
        if name.lower() == "check" or name.lower().startswith("check ("):
            continue
        contexts.append(name)
    if not contexts:
        raise AuditError(
            f"the Hard Gates table in {document} parsed to no contexts — the audit would claim "
            f"every gate is covered while covering nothing")
    duplicates = sorted({name for name in contexts if contexts.count(name) > 1})
    if duplicates:
        raise AuditError(f"{document} lists {duplicates} more than once in the Hard Gates table")
    return tuple(contexts)


def missing_hard_gates(gates: Sequence["Gate"] | None = None) -> tuple[str, ...]:
    """Hard gates with no entry in `gates` (default: the module-level registry) proving them."""
    registry = gates if gates is not None else GATES.values()
    covered = {gate.check for gate in registry if gate.check}
    return tuple(context for context in hard_gates() if context not in covered)


# The "valid lesson" every lesson-gate mutation starts from. It must pass the *strict* gate a new
# lesson gets (the copy lands outside the repository, so `lesson_gate.py` cannot place it on the
# base branch and applies the new-lesson rules: required sections, >= 400 chars, and the #1783
# structured fields). If it ever stops passing, the control run goes red and this audit says so —
# point the constant at another lesson rather than weakening the check.
BASELINE_LESSON = "lessons/contrib/docker-build-exit-137-multistage-oom.md"

# A fabricated source: `<owner>`/`<repo>` is a placeholder by construction, so the provenance gate
# can see it without touching the network (`classify()` decides this before any fetch).
FABRICATED_SOURCE_URL = "https://github.com/<owner>/<repo>/issues/1"

# The 404 repository that motivated the provenance gate itself: four lesson PRs (#1713–#1716)
# passed 24/24 checks while citing it (docs/maintainer/provenance-gate-2026-09-16.md). This
# mutation needs the network — offline, a failed fetch is `unknown`, and a gate must never fail on
# the absence of evidence — so it is skipped unless `--online` is given.
# If this URL ever starts resolving it is no longer a mutation: replace it and say why in
# docs/maintainer/gate-mutation-audit.md.
DEAD_SOURCE_URL = "https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652"


class AuditError(RuntimeError):
    """The audit cannot run (as opposed to "a gate cannot fail"). Exit code 2."""


class MutationError(RuntimeError):
    """A mutation did not apply — reported as an audit failure, never silently skipped."""


# ── Mutations ───────────────────────────────────────────────────────
def _sub(lesson: Path, pattern: str, repl: str, what: str) -> None:
    """Apply one regex substitution, or fail loudly if the pattern did not match.

    A mutation that quietly matches nothing would leave the gate green and be reported as
    "the gate cannot fail" — a false accusation. Raising here keeps the two failure modes
    apart in the report.
    """
    text = lesson.read_text(encoding="utf-8")
    mutated, matches = re.subn(pattern, repl, text, count=1)
    if matches != 1:
        raise MutationError(
            f"{what}: pattern {pattern!r} matched {matches} time(s) in {lesson.name} — "
            f"the mutation did not apply, so it proves nothing")
    lesson.write_text(mutated, encoding="utf-8")


def _mutate_strip_title(lesson: Path) -> None:
    """Delete the frontmatter `title:` line — the first required field of a lesson."""
    _sub(lesson, r"(?m)^title:[^\n]*\n", "", "delete title:")


def _mutate_noncanonical_domain(lesson: Path) -> None:
    """Replace `domain:` with a value that is not in the reviewed vocabulary."""
    _sub(lesson, r"(?m)^domain:[^\n]*$", "domain: not-a-canonical-domain", "non-canonical domain")


def _mutate_drop_required_section(lesson: Path) -> None:
    """Rename the `## Root Cause` heading so a required section is missing."""
    _sub(lesson, r"(?m)^##\s+Root Cause\b[^\n]*$", "## Background", "drop required section")


def _mutate_placeholder_source(lesson: Path) -> None:
    """Cite a fabricated (placeholder) source instead of a real one."""
    _sub(lesson, r"(?m)^source:[^\n]*$", f'source: "{FABRICATED_SOURCE_URL}"', "placeholder source")


def _mutate_json_placeholder_source(lesson: Path) -> None:
    """Hide the same fabricated source inside JSON-style frontmatter.

    This is the shape the provenance gate's own red-team probe found: the first version read
    `source:` line by line, so a quoted key inside a JSON block was invisible and a fabricated
    source could be hidden from the gate entirely (`_json_citations` exists because of it,
    docs/maintainer/provenance-gate-2026-09-16.md). A mutation that only ever re-tests the YAML
    path would not notice that regression coming back.
    """
    text = lesson.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise MutationError("json frontmatter: the lesson has no frontmatter block to convert")
    end = text.find("\n---", 3)
    if end == -1:
        raise MutationError("json frontmatter: the frontmatter block is not closed with `---`")
    frontmatter = text[3:end]
    title = re.search(r"(?m)^title:[ \t]*(.+)$", frontmatter)
    domain = re.search(r"(?m)^domain:[ \t]*(.+)$", frontmatter)
    if not title or not domain:
        raise MutationError("json frontmatter: could not read title/domain out of the YAML block")
    payload = {
        "title": title.group(1).strip().strip("'\""),
        "domain": domain.group(1).strip().strip("'\""),
        "source": FABRICATED_SOURCE_URL,
    }
    lesson.write_text(
        "---\n" + json.dumps(payload, indent=2, ensure_ascii=False) + "\n---" + text[end + 4:],
        encoding="utf-8")


def _mutate_high_evidence_no_source(lesson: Path) -> None:
    """Claim `evidence_level: E3` while citing nothing at all — the tier-2a path.

    The three mutations above all replace a URL with a *bad* URL, so they only ever reach
    `failures`. The tier-2 branch was therefore structurally invisible to this audit: it
    appended to `advisories`, which `check_provenance.main()` never folded into its exit
    code, so a new E2/E3 lesson with no source printed a ⚠️ and exited 0 — the branch could
    not fail (open-code-review §2.3, 2026-10-06). Rewriting the whole frontmatter block is
    what makes "cites nothing" unambiguous: the baseline lesson carries `source:` *and* a
    `provenance:` block, so deleting one line would leave a citation behind.
    """
    text = lesson.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise MutationError("high-evidence-no-source: the lesson has no frontmatter block")
    end = text.find("\n---", 3)
    if end == -1:
        raise MutationError("high-evidence-no-source: the frontmatter block is not closed with `---`")
    frontmatter = text[3:end]
    title = re.search(r"(?m)^title:[ \t]*(.+)$", frontmatter)
    domain = re.search(r"(?m)^domain:[ \t]*(.+)$", frontmatter)
    if not title or not domain:
        raise MutationError("high-evidence-no-source: could not read title/domain out of the "
                            "frontmatter block")
    lines = [f"title: {title.group(1).strip()}",
             f"domain: {domain.group(1).strip()}",
             "evidence_level: E3"]
    lesson.write_text("---\n" + "\n".join(lines) + "\n---" + text[end + 4:], encoding="utf-8")


def _mutate_dead_source(lesson: Path) -> None:
    """Cite a source that returns 404 — the case that motivated the gate.

    Offline this is unobservable by design (a network failure is `unknown`, never a failure), so
    the mutation is declared `network=True` and skipped unless `--online` is passed.
    """
    _sub(lesson, r"(?m)^source:[^\n]*$", f'source: "{DEAD_SOURCE_URL}"', "dead source")


# ── Scenarios for the hard gates whose verdict lives in a workflow ──────────────────────────────
#
# Everything below mutates a **gate's criterion**, not product code: the artifact is a throwaway
# scenario (a git history, a pytest project, a tree with a planted secret) and the gate's own step
# body — read out of the workflow YAML at run time — is executed against it. The repository tree is
# never written. A PR that deletes the criterion (the `5) … exit 1` arm, the `Signed-off-by:` grep)
# makes the mutation stay green, which is the finding this audit exists to produce.
class CriterionUnavailable(AuditError):
    """The gate's criterion could not be located or executed. Never a verdict (exit 3)."""


def _scenario(run_dir: Path) -> Path:
    """The directory a workflow-driven gate prepares for itself."""
    path = run_dir / "scenario"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# Token-shaped strings are built by concatenation, never written as literals: this file lives under
# `scripts/`, which `scripts/check_worker_secrets.py` scans. A literal would make the *audit job* red
# for the thing a mutation plants on purpose.
def _fake_github_token() -> str:
    return "ghp_" + "a1B2c3D4e5F6g7H8i9" + "J0k1L2m3N4o5P6q7R8"


def _fake_node_token() -> str:
    return "mcp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6"


# ── `DCO / Signed-off-by` ───────────────────────────────────────────
DCO_SIGNOFF = "Signed-off-by: Gate Mutation Audit <audit@example.invalid>"


def _prepare_dco_scenario(run_dir: Path) -> Path:
    """A real git history: one base commit outside the range, two commits the gate must scan."""
    scenario = _scenario(run_dir)
    payload = {
        "base": "chore: the commit the pull request branch starts from\n",
        "commits": [
            f"fix: first commit of the pull request\n\n{DCO_SIGNOFF}\n",
            f"fix: second commit of the pull request\n\n{DCO_SIGNOFF}\n",
        ],
    }
    _write_text(scenario / "commits.json", json.dumps(payload, indent=2) + "\n")
    return scenario


def _dco_payload(scenario: Path) -> dict:
    path = scenario / "commits.json"
    if not path.is_file():
        raise MutationError(f"the DCO scenario has no {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _without_signoff(message: str) -> str:
    lines = message.splitlines()
    kept = [line for line in lines if not line.strip().lower().startswith("signed-off-by:")]
    if len(kept) == len(lines):
        raise MutationError(f"the commit message has no Signed-off-by: trailer: {message!r}")
    return "\n".join(kept).rstrip("\n") + "\n"


def _mutate_dco_drop_tip(scenario: Path) -> None:
    """Remove the trailer from the tip commit of the pull request."""
    payload = _dco_payload(scenario)
    payload["commits"][-1] = _without_signoff(payload["commits"][-1])
    _write_text(scenario / "commits.json", json.dumps(payload, indent=2) + "\n")


def _mutate_dco_drop_middle(scenario: Path) -> None:
    """Remove the trailer from the first pull-request commit, leaving the tip signed.

    A gate that only reads `git log -1` stays green here, which is the failure this mutation exists
    to name: the DCO action reads the whole range (`git rev-list --no-merges base..head`).
    """
    payload = _dco_payload(scenario)
    payload["commits"][0] = _without_signoff(payload["commits"][0])
    _write_text(scenario / "commits.json", json.dumps(payload, indent=2) + "\n")


# ── `test (ubuntu-latest, 3.11)` ────────────────────────────────────
PYTEST_LEG_BASELINE = '''"""A one-test suite for the required cross-platform leg."""


def test_the_suite_runs():
    assert 1 + 1 == 2
'''

PYTEST_LEG_FAILING = '''"""The mutation: the suite runs and a test fails (`pytest` exit 1)."""


def test_the_suite_runs():
    assert 1 + 1 == 3
'''

PYTEST_LEG_COLLECTION_ERROR = '''"""The mutation: collection fails before a test runs.

`pytest` exits 2, the code that #2006/#2008 read as "passed" for eight legs.
"""

import a_module_that_does_not_exist_anywhere_xyz


def test_the_suite_runs():
    assert 1 + 1 == 2
'''

PYTEST_LEG_NO_TESTS = '''"""The mutation: the tree collects no tests at all (`pytest` exit 5).

Exit 5 is the one the first version of the leg read as green: "the suite never started" must never
be reported as "the suite passed".
"""


def helper():
    return 1
'''


def _prepare_pytest_leg(run_dir: Path) -> Path:
    scenario = _scenario(run_dir)
    _write_text(scenario / "tests" / "test_leg.py", PYTEST_LEG_BASELINE)
    return scenario


def _mutate_pytest_failing(scenario: Path) -> None:
    _write_text(scenario / "tests" / "test_leg.py", PYTEST_LEG_FAILING)


def _mutate_pytest_collection_error(scenario: Path) -> None:
    _write_text(scenario / "tests" / "test_leg.py", PYTEST_LEG_COLLECTION_ERROR)


def _mutate_pytest_no_tests(scenario: Path) -> None:
    _write_text(scenario / "tests" / "test_leg.py", PYTEST_LEG_NO_TESTS)


# ── `audit` (the required job that carries the secret scan, the worker suite and the floor) ──────
AUDIT_SECRET_SCANNERS = ("check_worker_secrets.py", "check_published_secrets.py")


def _prepare_audit_secret_scan(run_dir: Path) -> Path:
    """A minimal checkout the audit job's `Secret Scan` step can scan for real.

    The two scanners resolve their root from their own location (`REPO = script.parent.parent`), so
    copying them into `scenario/scripts/` points them at the scenario instead of this repository.
    """
    scenario = _scenario(run_dir)
    scripts = scenario / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for name in AUDIT_SECRET_SCANNERS:
        source = REPO / "scripts" / name
        if not source.is_file():
            raise AuditError(f"the secret scanner {_rel(source)} is missing")
        shutil.copyfile(source, scripts / name)
    _write_text(scenario / "workers" / "clean.mjs", "export const answer = 42;\n")
    _write_text(scenario / "docs" / "field-report.md",
                "# A field report\n\nNothing credential-shaped in here.\n")
    return scenario


def _mutate_audit_hardcoded_token(scenario: Path) -> None:
    """Plant a GitHub-token-shaped string in the worker source the scan reads.

    The line is assembled at run time, and the planted file is byte-for-byte what it was
    before. The reason is the scanner, not taste: the third-party scanner reads whole files
    and reports a quoted value assigned to a token-shaped *name* — so writing that shape in
    this source reports the repository against itself (alerts #381/#382, opened 2026-10-25),
    even though the value here is fake and only ever lands in a throwaway scenario. The
    audit's red path still depends on the scenario carrying a credential-shaped literal, so
    the shape is assembled rather than removed.
    """
    key = "tok" + "en"
    _write_text(scenario / "workers" / "leaky.mjs",
                f'export const client = {{ {key}: "{_fake_github_token()}" }};\n')


def _mutate_audit_published_token(scenario: Path) -> None:
    """Plant a node-token-shaped string in published prose (`docs/`, the #1982 surface)."""
    _write_text(
        scenario / "docs" / "field-report.md",
        "# A field report\n\nIt was sent with `Authorization: Bearer "
        f"{_fake_node_token()}`.\n")


WORKER_SUITE_BASELINE = '''import { test } from 'node:test';
import assert from 'node:assert/strict';

test('the worker answers', () => {
  assert.equal(1 + 1, 2);
});
'''

WORKER_SUITE_FAILING = '''import { test } from 'node:test';
import assert from 'node:assert/strict';

test('the worker answers', () => {
  assert.equal(1 + 1, 3);
});
'''


def _prepare_audit_worker_suite(run_dir: Path) -> Path:
    scenario = _scenario(run_dir)
    _write_text(scenario / "workers" / "worker.test.mjs", WORKER_SUITE_BASELINE)
    return scenario


def _mutate_audit_worker_suite(scenario: Path) -> None:
    _write_text(scenario / "workers" / "worker.test.mjs", WORKER_SUITE_FAILING)


def _coverage_criterion() -> tuple[float, str]:
    """`(--cov-fail-under, --cov=PACKAGE)` exactly as `pr-checks.yml` spells them.

    Read from the step, not restated here: the floor the mutation is aimed at is the floor the
    required `audit` job enforces. Comment lines are dropped first — the step's own comment talks
    about `--cov=misakanet` while explaining the accepted debt, and a whole-body regex would count it.
    """
    body = _workflow_step_body(PR_CHECKS_WORKFLOW, "audit", "Run Test Suite")
    code = "\n".join(line for line in body.splitlines() if not line.strip().startswith("#"))
    floors = re.findall(r"--cov-fail-under=(\d+(?:\.\d+)?)", code)
    packages = re.findall(r"--cov=([A-Za-z_][\w.]*)", code)
    if len(floors) != 1 or len(packages) != 1:
        raise CriterionUnavailable(
            f"expected exactly one --cov-fail-under= and one --cov= in the "
            f"`Run Test Suite` step of {_rel(PR_CHECKS_WORKFLOW)}; "
            f"found {floors} and {packages}")
    return float(floors[0]), packages[0]


def _prepare_audit_coverage_floor(run_dir: Path) -> Path:
    """A tiny project that is fully covered, plus the number a non-pytest-cov run compares."""
    scenario = _scenario(run_dir)
    floor, package = _coverage_criterion()
    if floor <= 0:
        raise AuditError(
            f"the coverage floor in {_rel(PR_CHECKS_WORKFLOW)} is {floor:g}, so the criterion "
            f"rejects nothing and cannot be mutated into failing — restore a floor above 0")
    _write_text(scenario / package / "__init__.py",
                '"""The package the floor is measured on."""\n\n\ndef add(left, right):\n'
                '    return left + right\n')
    _write_text(scenario / "tests" / "test_coverage.py",
                f'"""The valid project: the test exercises the measured package."""\n\n'
                f'from {package} import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n')
    _write_text(scenario / "coverage.json", json.dumps({"coverage": 100.0}, indent=2) + "\n")
    return scenario


def _mutate_audit_coverage_drop(scenario: Path) -> None:
    """Make the measured coverage fall below the floor `pr-checks.yml` enforces.

    The mutated observation is derived from the floor rather than hardcoded, so a floor that moves
    down does not silently leave the mutation green: at a floor of 0 nothing can be below it and
    this refuses to pretend (`MutationError`) instead of "proving" a criterion it no longer has.
    """
    floor, package = _coverage_criterion()
    if floor <= 0:
        raise MutationError(
            f"the coverage floor in {_rel(PR_CHECKS_WORKFLOW)} is {floor:g} — the criterion cannot "
            f"reject any coverage number, so there is nothing here that can go red")
    # The real path (pytest-cov installed): a test that never touches the package measures 0 %.
    _write_text(scenario / "tests" / "test_coverage.py",
                '"""The mutation: the package is never imported, so coverage is 0 %."""\n\n\n'
                'def test_add():\n    assert 1 + 1 == 2\n')
    # The modelled path (pytest-cov absent): the observation the floor is compared against.
    _write_text(scenario / "coverage.json",
                json.dumps({"coverage": max(floor - 1.0, 0.0)}, indent=2) + "\n")


# ── Executing a workflow's own verdict ──────────────────────────────
def _load_yaml(path: Path) -> dict:
    import yaml  # imported here: `_preflight()` owns the "PyYAML is missing" message

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:                       # noqa: BLE001 - reported as "cannot judge"
        raise CriterionUnavailable(f"could not read {_rel(path)} as YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise CriterionUnavailable(f"{_rel(path)} is not a YAML mapping")
    return data


def _workflow_step_body(workflow: Path, job: str, step_name: str) -> str:
    """The `run:` script of one step, exactly as the workflow spells it."""
    data = _load_yaml(workflow)
    jobs = data.get("jobs")
    if not isinstance(jobs, dict) or job not in jobs:
        raise CriterionUnavailable(f"{_rel(workflow)} has no job {job!r}")
    for step in (jobs[job] or {}).get("steps") or []:
        if step.get("name") == step_name:
            body = step.get("run")
            if not isinstance(body, str) or not body.strip():
                raise CriterionUnavailable(
                    f"{_rel(workflow)}/{job}/{step_name}: the step has no `run:` block")
            return body
    raise CriterionUnavailable(
        f"{_rel(workflow)}/{job} has no step named {step_name!r} — the gate's criterion moved, so "
        f"this mutation would test nothing. Point scripts/gate_mutation_audit.py at the new name.")


def _action_step_body(action: Path, step_id: str) -> str:
    """The `run:` script of one step of a composite action (`runs.steps`), by `id:`."""
    data = _load_yaml(action)
    for step in (data.get("runs") or {}).get("steps") or []:
        if step.get("id") == step_id:
            body = step.get("run")
            if isinstance(body, str) and body.strip():
                return body
    raise CriterionUnavailable(
        f"{_rel(action)} has no composite step with `id: {step_id}` — the criterion this mutation "
        f"executes moved, so it would prove nothing")


_EXPRESSION = re.compile(r"\$\{\{\s*(.+?)\s*\}\}")


def _render(body: str, values: dict[str, str], *, where: str) -> str:
    """Substitute `${{ … }}` inputs strictly: a missing value is not an empty input.

    GitHub substitutes the event context; here the value comes from the scenario. Running a step
    with an empty input would judge a different gate than the one the repository ships, which is the
    silent drift this whole audit exists to prevent.
    """

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key not in values:
            raise CriterionUnavailable(
                f"{where}: the step uses `${{{{ {key} }}}}` and this audit has no value for it")
        return values[key]

    return _EXPRESSION.sub(substitute, body)


def _base_env(scenario: Path) -> dict[str, str]:
    env = os.environ.copy()
    dirs = [os.path.dirname(sys.executable)]
    node = shutil.which("node")
    if node:
        dirs.append(os.path.dirname(node))
    env["PATH"] = os.pathsep.join([entry for entry in (*dirs, env.get("PATH", "")) if entry])
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # An outer pytest invocation's flags must not change the criterion this audit is executing.
    env.pop("PYTEST_ADDOPTS", None)
    env.setdefault("HOME", str(scenario))
    env.setdefault("GITHUB_WORKSPACE", str(scenario))
    return env


def _find_bash() -> str | None:
    """A bash to execute a step body with, including GitHub's Windows runners' Git Bash.

    `shutil.which` covers ubuntu/macOS and any Windows shell where Git is on PATH; the fallback
    paths cover the Windows runner, where the Actions `bash` shell resolves `bash.exe` from Git for
    Windows even when `bash` is not on PATH for a `pwsh` step. None means the criterion cannot be
    executed, which is reported as "cannot judge" — never as a red gate.
    """
    found = shutil.which("bash")
    if found:
        return found
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
        Path(os.environ.get("ProgramW6432", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "bin" / "bash.exe",
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def _bash(body: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    """Run a step body the way GitHub does (`shell: bash` = `bash -eo pipefail <script>`)."""
    exe = _find_bash()
    if exe is None:
        raise CriterionUnavailable(
            "no bash found on this machine — the workflow step body cannot be executed, and an "
            "unevaluated criterion is not a red gate")
    return subprocess.run(
        [exe, "--noprofile", "--norc", "-eo", "pipefail", "-c", body],
        cwd=str(cwd), env=env, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=DEFAULT_TIMEOUT)


def _git_env(scenario: Path) -> dict[str, str]:
    env = _base_env(scenario)
    env.update({
        "GIT_AUTHOR_NAME": "Gate Mutation Audit",
        "GIT_AUTHOR_EMAIL": "audit@example.invalid",
        "GIT_COMMITTER_NAME": "Gate Mutation Audit",
        "GIT_COMMITTER_EMAIL": "audit@example.invalid",
        # The machine's global config must not reach the scenario: `commit.gpgsign = true` would
        # make the commit fail and the audit would report the gate as broken.
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    })
    return env


def _git(argv: list[str], cwd: Path, env: dict[str, str], *,
         stdin: str | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *argv], cwd=str(cwd), env=env, input=stdin,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=DEFAULT_TIMEOUT)
    if proc.returncode != 0:
        raise CriterionUnavailable(
            f"`git {' '.join(argv[:2])}` failed ({proc.returncode}) in the scenario: "
            f"{proc.stderr.strip()[:400]}")
    return proc


def _github_output(path: Path) -> dict[str, str]:
    """The single-line `key=value` outputs an executed step wrote to `$GITHUB_OUTPUT`."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value
    return values


def _require_text(path: Path, needle: str, what: str) -> None:
    """Pin the destination of a verdict: what turns the criterion's answer into a red check."""
    if needle not in path.read_text(encoding="utf-8"):
        raise CriterionUnavailable(
            f"{_rel(path)} no longer contains {needle!r} — {what} moved or was relaxed. Update "
            f"the mutation with the gate; otherwise this audit is judging a rule that no longer "
            f"blocks a merge.")


def _drive_dco(scenario: Path) -> int:
    """Execute the DCO audit's own `Scan DCO` step against a real git history."""
    _require_text(PR_CHECKS_WORKFLOW, "steps.dco.outputs.dco-passed == 'false'",
                  "the audit job's DCO verdict")
    _require_text(DCO_WORKFLOW, "conclusion: pass ? 'success' : 'failure'",
                  "the `DCO / Signed-off-by` check's conclusion")

    payload = _dco_payload(scenario)
    base_message = payload.get("base")
    messages = payload.get("commits")
    if not isinstance(base_message, str) or not isinstance(messages, list) or not messages:
        raise CriterionUnavailable(
            "the DCO scenario needs a `base` string and a non-empty `commits` list")

    repo = scenario / "repo"
    repo.mkdir(exist_ok=True)
    env = _git_env(scenario)
    _git(["init", "-q"], repo, env)
    shas: list[str] = []
    for message in [base_message, *messages]:
        _git(["commit", "-q", "--allow-empty", "--no-gpg-sign", "-F", "-"], repo, env,
             stdin=str(message))
        shas.append(_git(["rev-parse", "HEAD"], repo, env).stdout.strip())
    base, head = shas[0], shas[-1]

    output = scenario / "github_output"
    output.write_text("", encoding="utf-8")
    env["GITHUB_OUTPUT"] = str(output)
    body = _render(_action_step_body(DCO_ACTION, "scan"),
                   {"inputs.base-sha": base, "inputs.head-sha": head},
                   where=_rel(DCO_ACTION))
    proc = _bash(body, repo, env)
    print(proc.stdout)
    if proc.returncode != 0:
        raise CriterionUnavailable(
            f"the DCO scan step itself exited {proc.returncode}: {proc.stderr.strip()[:400]}")
    verdict = _github_output(output).get("dco_passed")
    if verdict not in ("true", "false"):
        raise CriterionUnavailable(f"the DCO scan wrote no usable `dco_passed` output: {verdict!r}")
    return 0 if verdict == "true" else 1


def _drive_pytest_leg(scenario: Path) -> int:
    """Run the `test (ubuntu-latest, 3.11)` leg's own two steps: pytest, then its verdict."""
    run_step = _workflow_step_body(CROSS_PLATFORM_WORKFLOW, "test", "Run Tests")
    verify_step = _workflow_step_body(CROSS_PLATFORM_WORKFLOW, "test", "Verify test outcome")

    output = scenario / "github_output"
    output.write_text("", encoding="utf-8")
    env = _base_env(scenario)
    env["GITHUB_OUTPUT"] = str(output)
    env["PYTHONPATH"] = str(scenario)
    proc = _bash(run_step, scenario, env)
    print(proc.stdout)
    if proc.returncode != 0:
        raise CriterionUnavailable(f"the `Run Tests` step itself exited {proc.returncode}")
    pytest_exit = _github_output(output).get("pytest_exit", "").strip()
    if not re.fullmatch(r"\d{1,3}", pytest_exit):
        # An empty or malformed code would make the `case` fall through to `*)`, i.e. red for a
        # reason the criterion never expressed. Say the truth instead of borrowing the verdict.
        raise CriterionUnavailable(
            f"`Run Tests` recorded {pytest_exit!r} as pytest_exit — that is not an exit code")
    if pytest_exit == "127":
        raise CriterionUnavailable(
            "pytest is not on PATH, so exit 127 would read as the gate rejecting the suite — it "
            "is the environment failing to run it")
    verdict = _render(verify_step, {"steps.test.outputs.pytest_exit": pytest_exit},
                      where=f"{_rel(CROSS_PLATFORM_WORKFLOW)}::Verify test outcome")
    proc = _bash(verdict, scenario, env)
    print(proc.stdout)
    if proc.returncode not in (0, 1):
        raise CriterionUnavailable(
            f"the verdict step exited {proc.returncode}; its criterion only produces 0 or 1")
    return proc.returncode


def _drive_audit_secret_scan(scenario: Path) -> int:
    """Execute the audit job's `Secret Scan` step over a scenario tree."""
    for name in AUDIT_SECRET_SCANNERS:
        if not (scenario / "scripts" / name).is_file():
            raise CriterionUnavailable(f"the scenario is missing scripts/{name}")
    output = scenario / "github_output"
    output.write_text("", encoding="utf-8")
    env = _base_env(scenario)
    env["GITHUB_OUTPUT"] = str(output)
    proc = _bash(_workflow_step_body(PR_CHECKS_WORKFLOW, "audit", "Secret Scan"), scenario, env)
    print(proc.stdout)
    combined = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return 0
    # Only the criterion's own sentence counts as a red. A scanner that crashed, a missing copy or
    # a broken scenario exits non-zero too, and crediting the gate for that would be a false pass.
    if ("Secret scan found hardcoded secrets" in combined
            and "Traceback (most recent call last)" not in combined):
        return 1
    raise CriterionUnavailable(
        f"the `Secret Scan` step exited {proc.returncode} without its verdict sentence")


def _drive_audit_worker_suite(scenario: Path) -> int:
    """Execute the audit job's `Run Worker Test Suite (node)` step over a scenario tree."""
    if shutil.which("node") is None:
        raise CriterionUnavailable("node is not installed — the worker suite cannot be judged")
    _require_text(PR_CHECKS_WORKFLOW, "steps.node_tests.outcome",
                  "the audit job's worker-suite verdict")
    output = scenario / "github_output"
    output.write_text("", encoding="utf-8")
    env = _base_env(scenario)
    env["GITHUB_OUTPUT"] = str(output)
    proc = _bash(
        _workflow_step_body(PR_CHECKS_WORKFLOW, "audit", "Run Worker Test Suite (node)"),
        scenario, env)
    print(proc.stdout)
    combined = proc.stdout + proc.stderr
    if proc.returncode == 0:
        # A green suite that ran no tests is the #2006 failure shape: prove it ran one.
        if not re.search(r"^# pass [1-9]", combined, re.MULTILINE):
            raise CriterionUnavailable(
                "the worker suite exited 0 without running a test — a green run here would prove "
                "nothing")
        return 0
    if proc.returncode == 127 or "command not found" in combined:
        raise CriterionUnavailable("node could not be executed in the scenario")
    if not re.search(r"^# fail [1-9]", combined, re.MULTILINE) and "not ok" not in combined:
        raise CriterionUnavailable(
            f"the worker suite exited {proc.returncode} without reporting a failing test")
    return 1


def _drive_audit_coverage_floor(scenario: Path) -> int:
    """Evaluate the audit job's coverage floor against a scenario project.

    With `pytest-cov` installed (the CI job installs it) this runs the plugin with the workflow's own
    flags: a real mutation of the floor. Without it, the floor is compared here against the
    scenario's coverage number — a criterion-level stub, and the one place in this registry where
    that is true. Either way the *number* comes from `pr-checks.yml`, so lowering it below the
    mutation turns the audit red instead of silently re-baselining the proof.
    """
    floor, package = _coverage_criterion()
    if not (scenario / "tests" / "test_coverage.py").is_file():
        raise CriterionUnavailable("the scenario has no tests/test_coverage.py")
    if importlib.util.find_spec("pytest_cov") is not None:
        env = _base_env(scenario)
        env["COVERAGE_FILE"] = str(scenario / ".coverage")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", f"--cov={package}", f"--cov-fail-under={floor:g}",
             "tests/"],
            cwd=str(scenario), env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=DEFAULT_TIMEOUT)
        print(proc.stdout)
        combined = proc.stdout + proc.stderr
        if proc.returncode == 0:
            if "coverage:" not in combined:
                raise CriterionUnavailable(
                    "pytest exited 0 without a coverage report — the floor was not evaluated")
            return 0
        if "Required test coverage of" in combined:
            return 1
        raise CriterionUnavailable(
            f"pytest --cov-fail-under exited {proc.returncode} without its coverage verdict")
    recorded = json.loads((scenario / "coverage.json").read_text(encoding="utf-8"))
    observed = float(recorded["coverage"])
    print(f"coverage floor: modelled comparison (pytest-cov is not installed): "
          f"{observed:g}% against the {floor:g}% floor in {_rel(PR_CHECKS_WORKFLOW)}")
    return 0 if observed >= floor else 1


_DRIVERS: dict[str, Callable[[Path], int]] = {
    "dco": _drive_dco,
    "pytest-leg": _drive_pytest_leg,
    "audit-secret-scan": _drive_audit_secret_scan,
    "audit-worker-suite": _drive_audit_worker_suite,
    "audit-coverage-floor": _drive_audit_coverage_floor,
}


def _drive(spec: str, scenario: Path) -> int:
    """Internal entry point (`--_drive SPEC SCENARIO`): judge one scenario, as a real process.

    Exit 0 = the gate accepted the scenario, 1 = the gate rejected it, 3 = the criterion could not
    be evaluated. Printing the criterion's own output is deliberate: on a red the parent quotes the
    line that says why, and a reader can tell which rule fired.
    """
    driver = _DRIVERS.get(spec)
    if driver is None:
        print(f"internal: unknown driver {spec!r}", file=sys.stderr)
        return EXIT_CANNOT_JUDGE
    if not scenario.is_dir():
        print(f"internal: the scenario {scenario} is not a directory", file=sys.stderr)
        return EXIT_CANNOT_JUDGE
    try:
        return driver(scenario)
    except CriterionUnavailable as exc:
        print(f"CANNOT JUDGE: {exc}", file=sys.stderr)
        return EXIT_CANNOT_JUDGE
    except Exception as exc:                       # noqa: BLE001 - a driver crash is not a verdict
        print(f"CANNOT JUDGE: the driver crashed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_CANNOT_JUDGE


# ── Gate definitions ────────────────────────────────────────────────
@dataclass(frozen=True)
class Mutation:
    """One deliberate break of the thing a gate checks."""

    name: str
    description: str
    apply: Callable[[Path], None]
    network: bool = False


@dataclass(frozen=True)
class Gate:
    """A gate under audit, plus how to give it something valid to reject.

    `check` is the required-status-check context this gate proves, spelled exactly as
    `docs/ci-gates.md` spells it; a full run fails when any context in that table has no gate
    naming it. `why` is required when `check` is `None`: an entry that is not a hard gate has to say
    why it is in the audit anyway, or it is just a gate nobody asked to prove.
    """

    name: str
    description: str
    script: Path                                 # the executable the criterion lives in
    command: Callable[[Path, bool], list[str]]   # (artifact, online) -> argv
    mutations: tuple[Mutation, ...]
    prepare: Callable[[Path], Path]              # (run_dir) -> the valid artifact (file or dir)
    check: str | None = None                     # hard-gate context from docs/ci-gates.md
    why: str = ""                                # required when check is None


def _prepare_baseline_lesson(run_dir: Path) -> Path:
    """Copy `BASELINE_LESSON` into `run_dir/lessons/contrib/…` and return the copy.

    It keeps its path *shape* (`lessons/<sub>/<name>.md`) because the lesson gate keys two rules
    off it: only a path inside a lesson tree gets the strict #1783 structured-field tier, and
    same-stem files are treated as translation mirrors, so copying the lesson does not look like
    a duplicate title. The copy lives in a temp directory outside the repository, which is also
    why the gate applies the strict new-lesson rules rather than the advisory legacy ones.
    """
    source = REPO / BASELINE_LESSON
    if not source.is_file():
        raise AuditError(
            f"baseline lesson {BASELINE_LESSON} does not exist — point BASELINE_LESSON at a lesson "
            f"that passes the strict lesson gate (see docs/maintainer/gate-mutation-audit.md)")
    target = run_dir / BASELINE_LESSON
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def _lesson_gate_command(lesson: Path, online: bool) -> list[str]:
    return [sys.executable, str(LESSON_GATE), str(lesson)]


def _provenance_gate_command(lesson: Path, online: bool) -> list[str]:
    # `--strict-new <lesson>` is how CI runs this gate, and without it the tier-2 branch
    # never runs at all — so a mutation that only breaks tier 2 could not be observed.
    argv = [sys.executable, str(PROVENANCE_GATE), "--check"]
    if not online:
        argv.append("--offline")
    argv += ["--strict-new", str(lesson)]
    return argv


def _workflow_gate_command(spec: str) -> Callable[[Path, bool], list[str]]:
    """A command that re-enters this script as a real process to judge one workflow-driven gate."""

    def command(scenario: Path, online: bool) -> list[str]:
        return [sys.executable, str(SELF), "--_drive", spec, str(scenario)]

    return command


GATES: dict[str, Gate] = {
    "lesson-gate": Gate(
        name="lesson-gate",
        check="gate",
        description="structural gate for lessons: required frontmatter, sections, domain vocabulary",
        script=LESSON_GATE,
        prepare=_prepare_baseline_lesson,
        command=_lesson_gate_command,
        mutations=(
            Mutation("strip-title",
                     "delete the frontmatter `title:` line (a required field)",
                     _mutate_strip_title),
            Mutation("noncanonical-domain",
                     "replace `domain:` with a value outside data/domains.json",
                     _mutate_noncanonical_domain),
            Mutation("drop-required-section",
                     "rename the `## Root Cause` heading so a required section is missing",
                     _mutate_drop_required_section),
        ),
    ),
    "dco": Gate(
        name="dco",
        check="DCO / Signed-off-by",
        description=("every commit in the pull request range carries `Signed-off-by:` "
                     "(the dco-audit composite action, and the check `dco-check.yml` reports)"),
        script=DCO_ACTION,
        prepare=_prepare_dco_scenario,
        command=_workflow_gate_command("dco"),
        mutations=(
            Mutation("unsigned-tip-commit",
                     "remove `Signed-off-by:` from the last commit of the range",
                     _mutate_dco_drop_tip),
            Mutation("unsigned-middle-commit",
                     "remove `Signed-off-by:` from an earlier commit while the tip stays signed "
                     "(a gate that only reads HEAD stays green)",
                     _mutate_dco_drop_middle),
        ),
    ),
    "pytest-leg": Gate(
        name="pytest-leg",
        check="test (ubuntu-latest, 3.11)",
        description=("the pytest suite on the required `ubuntu-latest` + 3.11 leg, and the step "
                     "that turns pytest's exit code into that leg's verdict"),
        script=CROSS_PLATFORM_WORKFLOW,
        prepare=_prepare_pytest_leg,
        command=_workflow_gate_command("pytest-leg"),
        mutations=(
            Mutation("failing-test",
                     "make one test fail (`pytest` exit 1)", _mutate_pytest_failing),
            Mutation("collection-error",
                     "import a module that does not exist, so collection fails (`pytest` exit 2)",
                     _mutate_pytest_collection_error),
            Mutation("no-tests-collected",
                     "leave a file that collects no tests (`pytest` exit 5 — the leg used to "
                     "report that as green, #2006/#2008)",
                     _mutate_pytest_no_tests),
        ),
    ),
    "audit-secret-scan": Gate(
        name="audit-secret-scan",
        check="audit",
        description=("the required `audit` job's secret scan: `check_worker_secrets.py` and "
                     "`check_published_secrets.py`, both consumed through the job's `exit 1`"),
        script=PR_CHECKS_WORKFLOW,
        prepare=_prepare_audit_secret_scan,
        command=_workflow_gate_command("audit-secret-scan"),
        mutations=(
            Mutation("hardcoded-token-in-worker",
                     "plant a GitHub-token-shaped string in a scanned worker file",
                     _mutate_audit_hardcoded_token),
            Mutation("token-in-published-prose",
                     "plant a node-token-shaped string in published prose (`docs/`, #1982)",
                     _mutate_audit_published_token),
        ),
    ),
    "audit-worker-suite": Gate(
        name="audit-worker-suite",
        check="audit",
        description=("the required `audit` job's `node --test 'workers/**/*.test.mjs'` step — the "
                     "only automated verification of the MCP worker"),
        script=PR_CHECKS_WORKFLOW,
        prepare=_prepare_audit_worker_suite,
        command=_workflow_gate_command("audit-worker-suite"),
        mutations=(
            Mutation("failing-worker-test",
                     "make a worker test fail (`node --test` exits non-zero)",
                     _mutate_audit_worker_suite),
        ),
    ),
    "audit-coverage-floor": Gate(
        name="audit-coverage-floor",
        check="audit",
        description=("the required `audit` job's `pytest --cov-fail-under=` floor — the criterion "
                     "that is supposed to notice coverage falling"),
        script=PR_CHECKS_WORKFLOW,
        prepare=_prepare_audit_coverage_floor,
        command=_workflow_gate_command("audit-coverage-floor"),
        mutations=(
            Mutation("coverage-below-the-floor",
                     "drop measured coverage below the floor `pr-checks.yml` passes to pytest",
                     _mutate_audit_coverage_drop),
        ),
    ),
    "provenance-gate": Gate(
        name="provenance-gate",
        check=None,
        why=("not a required context in docs/ci-gates.md, and it is kept here on purpose: it is "
             "the only gate that reads whether a cited source exists — `gate` checks lesson "
             "structure and never fetches a URL — and because it cannot block a merge, a "
             "regression in it would otherwise be invisible. Proving it can still fail is the "
             "reason this audit exists."),
        description="does the source a lesson cites actually exist (placeholder / dead URLs)",
        script=PROVENANCE_GATE,
        prepare=_prepare_baseline_lesson,
        command=_provenance_gate_command,
        mutations=(
            Mutation("placeholder-source",
                     "cite a fabricated source (`<owner>`/`<repo>` placeholder URL)",
                     _mutate_placeholder_source),
            Mutation("placeholder-source-json-frontmatter",
                     "hide the same fabricated source in JSON-style frontmatter "
                     "(the 2026-09-16 red-team blind spot)",
                     _mutate_json_placeholder_source),
            Mutation("high-evidence-no-source",
                     "claim `evidence_level: E3` with no source at all (the tier-2 branch, "
                     "which advisories-only left unfailable)",
                     _mutate_high_evidence_no_source),
            Mutation("dead-source",
                     f"cite the 404 repository from the 2026-09-16 incident ({DEAD_SOURCE_URL})",
                     _mutate_dead_source,
                     network=True),
        ),
    ),
}


# ── Results ─────────────────────────────────────────────────────────
# Outcomes. `red` is the only one that counts as success — everything else means the audit could
# not observe a gate failing, which is the failure mode this whole script exists to surface.
OUTCOME_RED = "red"                  # the gate exited non-zero: it can still fail
OUTCOME_GREEN = "green"              # the gate exited 0 under its mutation: it cannot fail
OUTCOME_SKIPPED = "skipped"          # a network mutation without --online
OUTCOME_NOT_APPLIED = "not-applied"  # the mutation matched nothing / left the file unchanged
OUTCOME_TIMEOUT = "timeout"          # the gate did not finish
OUTCOME_ERROR = "error"              # the gate could not be executed

_MARKS = {
    OUTCOME_RED: "RED ✅",
    OUTCOME_GREEN: "GREEN ❌",
    OUTCOME_SKIPPED: "SKIP ⏭",
    OUTCOME_NOT_APPLIED: "NOT APPLIED ❌",
    OUTCOME_TIMEOUT: "TIMEOUT ❌",
    OUTCOME_ERROR: "ERROR ❌",
}

_PRIMARY_EVIDENCE_RE = re.compile(r"❌|^\s*-\s+\S")
_SECONDARY_EVIDENCE_RE = re.compile(
    r"FAIL|error|missing required|not in allowed|placeholder|does not resolve", re.IGNORECASE)


@dataclass
class MutationResult:
    """One gate run: either the control run (`mutation is None`) or a mutated one."""

    outcome: str
    mutation: Mutation | None = None
    returncode: int | None = None
    output: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome in (OUTCOME_RED, OUTCOME_SKIPPED)


@dataclass
class GateResult:
    gate: Gate
    control_ok: bool = False
    control_returncode: int | None = None
    control_output: str = ""
    mutations: list[MutationResult] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.control_ok and all(m.ok for m in self.mutations)

    @property
    def red(self) -> int:
        return sum(1 for m in self.mutations if m.outcome == OUTCOME_RED)

    @property
    def skipped(self) -> int:
        return sum(1 for m in self.mutations if m.outcome == OUTCOME_SKIPPED)

    def failures(self) -> list[str]:
        """One line per reason this gate did not prove it can fail."""
        failures = []
        if self.error:
            failures.append(
                f"gate {self.gate.name!r} could not be audited: {self.error}")
            return failures
        if not self.control_ok:
            failures.append(
                f"gate {self.gate.name!r} is RED on the unmutated baseline (exit "
                f"{self.control_returncode}) — the mutations prove nothing until the baseline "
                f"artifact passes again: {_evidence(self.control_output) or 'no output'}")
        for result in self.mutations:
            name = result.mutation.name if result.mutation else "?"
            description = result.mutation.description if result.mutation else ""
            if result.outcome == OUTCOME_GREEN:
                failures.append(
                    f"gate {self.gate.name!r} stayed GREEN under mutation "
                    f"{name!r} ({description}) — this gate cannot fail. A gate that cannot fail "
                    f"reports ✅ on broken input; fix the gate or delete it.")
            elif result.outcome == OUTCOME_NOT_APPLIED:
                failures.append(
                    f"gate {self.gate.name!r}: mutation {name!r} did not apply "
                    f"({result.detail}) — update the mutation in "
                    f"scripts/gate_mutation_audit.py; an unapplied mutation proves nothing")
            elif result.outcome == OUTCOME_TIMEOUT:
                failures.append(
                    f"gate {self.gate.name!r} did not finish within {result.detail} under mutation "
                    f"{name!r} — a hanging gate is not a passing gate")
            elif result.outcome == OUTCOME_ERROR:
                failures.append(
                    f"gate {self.gate.name!r} could not be executed under mutation "
                    f"{name!r}: {result.detail}")
        return failures


@dataclass
class AuditReport:
    results: list[GateResult]
    # The hard-gate contexts this run was supposed to prove, or None for a `--gate` subset run
    # (which makes no claim about coverage). Read from docs/ci-gates.md, never restated.
    hard_gates: tuple[str, ...] | None = None

    @property
    def uncovered(self) -> tuple[str, ...]:
        """Hard gates this run did not prove — a required check nobody showed can fail."""
        if self.hard_gates is None:
            return ()
        covered = {result.gate.check for result in self.results if result.gate.check}
        return tuple(context for context in self.hard_gates if context not in covered)

    @property
    def ok(self) -> bool:
        # An empty run is not a pass: "ran zero tests and printed ✅" is #2006/#2008, the very
        # failure mode this audit exists to catch, one level up. Nor is "every gate I ran passed"
        # a pass when a required context has no gate at all.
        return (bool(self.results) and not self.uncovered
                and all(result.ok for result in self.results))

    @property
    def failures(self) -> list[str]:
        failures: list[str] = []
        if not self.results:
            failures.append(
                "no gate was audited at all — auditing nothing is not a pass (#2006/#2008)")
        if self.uncovered:
            failures.append(
                "hard gate(s) in docs/ci-gates.md with no mutation in GATES: "
                + ", ".join(repr(context) for context in self.uncovered)
                + " — a required check nobody has proven can fail. Add a Gate(check=…) for each; "
                  "docs/ci-gates.md is the single source of the list, so the registry follows it.")
        failures.extend(line for result in self.results for line in result.failures())
        return failures

    def render(self) -> str:
        lines: list[str] = []
        if self.hard_gates is not None:
            covered = len(self.hard_gates) - len(self.uncovered)
            lines.append(
                f"hard gates: {covered}/{len(self.hard_gates)} covered — the list is parsed from "
                f"{_rel(HARD_GATES_DOC)}, not repeated here")
            lines.append("")
        for result in self.results:
            context = (f" [required: {result.gate.check}]" if result.gate.check
                       else " [not a hard gate]")
            lines.append(f"# {result.gate.name}{context} — {result.gate.description}")
            lines.append(f"  criterion: {_rel(result.gate.script)}")
            if result.error:
                lines.append(f"  control: ❌ could not run — {result.error}")
                lines.append("")
                continue
            control = ("✅ GREEN (exit 0): the unmutated artifact passes, so a red below is "
                       "caused by the mutation")
            if not result.control_ok:
                control = (f"❌ RED (exit {result.control_returncode}): the baseline artifact is "
                           f"already failing — {_evidence(result.control_output) or 'no output'}")
            lines.append(f"  control (unmutated): {control}")
            for mutation_run in result.mutations:
                mark = _MARKS.get(mutation_run.outcome, mutation_run.outcome)
                mutation = mutation_run.mutation
                label = f"{mutation.name} (network)" if mutation.network else mutation.name
                detail = ""
                if mutation_run.outcome == OUTCOME_RED:
                    detail = f" — exit {mutation_run.returncode}: {_evidence(mutation_run.output)}"
                elif mutation_run.outcome == OUTCOME_SKIPPED:
                    detail = " — needs the network; rerun with --online"
                elif mutation_run.detail:
                    detail = f" — {mutation_run.detail}"
                lines.append(f"  mutation {label:<38} {mark}{detail}")
                lines.append(f"      broke: {mutation.description}")
            lines.append("")

        total = sum(len(r.mutations) for r in self.results)
        red = sum(r.red for r in self.results)
        skipped = sum(r.skipped for r in self.results)
        lines.append(
            f"mutation audit: {len(self.results)} gate(s), {total} mutation(s) — "
            f"{red} red (as required), {skipped} skipped (network), "
            f"{total - red - skipped} that did not prove the gate can fail")
        if self.ok:
            lines.append("mutation audit: OK — every covered gate still goes red when the thing "
                         "it guards is broken")
        else:
            lines.append("mutation audit: FAILED — a green gate is the suspicious outcome:")
            for failure in self.failures:
                lines.append(f"  ❌ {failure}")
        return "\n".join(lines)


# ── Running ─────────────────────────────────────────────────────────
def _rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def _inside_repo(path: Path) -> bool:
    try:
        Path(path).resolve().relative_to(REPO.resolve())
        return True
    except ValueError:
        return False


def _evidence(output: str, limit: int = 160) -> str:
    """The line of a gate's output that shows *why* it failed.

    Two passes, because both gates print a summary line before their findings: the reason
    ("  - missing required field: title", "❌ …: source is a placeholder") is what a reader
    needs, not the count.
    """
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for pattern in (_PRIMARY_EVIDENCE_RE, _SECONDARY_EVIDENCE_RE):
        for line in lines:
            if pattern.search(line):
                return line[:limit]
    return lines[0][:limit] if lines else ""


def run_gate(gate: Gate, *, online: bool = False, timeout: float = DEFAULT_TIMEOUT,
             verbose: bool = False) -> GateResult:
    """Audit one gate: control run, then one run per mutation.

    Every artifact lives under a fresh temp directory outside the repository; the mutated lesson
    path is asserted to be outside the repository before and after the mutation is applied, so a
    bug in a mutation cannot reach the corpus.
    """
    result = GateResult(gate=gate)
    if not gate.script.is_file():
        result.error = f"gate script not found: {gate.script}"
        return result

    if _inside_repo(Path(tempfile.gettempdir())):
        result.error = (f"the temp directory ({tempfile.gettempdir()}) is inside the repository: "
                        f"mutations must never happen in the repository tree")
        return result

    with tempfile.TemporaryDirectory(prefix="gate-mutation-audit-") as raw:
        workdir = Path(raw)
        if _inside_repo(workdir):
            result.error = f"temp workdir {workdir} is inside the repository — refusing to mutate"
            return result

        control = _run_once(gate, workdir / "control", None, online=online, timeout=timeout)
        if control.outcome in (OUTCOME_RED, OUTCOME_GREEN):
            # `red`/`green` here only name the exit status of the control run: for the control the
            # useful reading is inverted (green = the baseline artifact is valid), and the report
            # says which way round it is.
            result.control_ok = control.returncode == 0
            result.control_returncode = control.returncode
            result.control_output = control.output
        else:
            result.error = control.detail or f"the control run did not execute ({control.outcome})"
            return result

        for index, mutation in enumerate(gate.mutations):
            if mutation.network and not online:
                result.mutations.append(MutationResult(
                    mutation=mutation, outcome=OUTCOME_SKIPPED,
                    detail="network mutation: needs --online"))
                continue
            run = _run_once(gate, workdir / f"mutation-{index}", mutation, online=online,
                            timeout=timeout)
            if verbose and run.output:
                print(f"--- {gate.name}/{mutation.name} full output ---\n{run.output.rstrip()}",
                      file=sys.stderr)
            result.mutations.append(run)

    return result


def _run_once(gate: Gate, run_dir: Path, mutation: Mutation | None, *, online: bool,
              timeout: float) -> MutationResult:
    """Materialize the artifact, optionally mutate it, and run the gate once.

    `mutation is None` is the control run: the same artifact, untouched.
    """
    try:
        artifact = Path(gate.prepare(run_dir))
    except Exception as exc:                       # noqa: BLE001 - reported, never raised
        return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                              detail=f"could not prepare the artifact: {exc}")

    if _inside_repo(artifact):
        return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                              detail=f"the artifact to mutate is inside the repository: {artifact}")

    if mutation is not None:
        try:
            before = _snapshot(artifact)
        except OSError as exc:
            return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                                  detail=f"could not read the artifact to mutate: {exc}")
        try:
            mutation.apply(artifact)
        except Exception as exc:                   # noqa: BLE001 - a mutation that did not apply
            return MutationResult(mutation=mutation, outcome=OUTCOME_NOT_APPLIED,
                                  detail=f"{type(exc).__name__}: {exc}")
        try:
            unchanged = _snapshot(artifact) == before
        except OSError as exc:
            return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                                  detail=f"the mutation removed the artifact: {exc}")
        if unchanged:
            return MutationResult(
                mutation=mutation, outcome=OUTCOME_NOT_APPLIED,
                detail="the mutation left the artifact byte-identical (a silent no-op)")
        if _inside_repo(artifact):
            return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                                  detail="the mutation moved the artifact into the repository: "
                                         f"{artifact}")

    argv = gate.command(artifact, online)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return MutationResult(mutation=mutation, outcome=OUTCOME_TIMEOUT, detail=f"{timeout:g}s")
    except OSError as exc:
        return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                              detail=f"could not run {argv[0]}: {exc}")

    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == EXIT_CANNOT_JUDGE:
        # "The criterion could not be evaluated" is not "the gate went red": a renamed step, a
        # missing value or a crashed driver must never be counted as proof that the gate has teeth.
        return MutationResult(
            mutation=mutation, outcome=OUTCOME_ERROR, returncode=proc.returncode, output=output,
            detail="the gate's criterion could not be evaluated (exit 3): "
                   + (_evidence(output, 400) or "no output"))
    return MutationResult(
        mutation=mutation,
        outcome=OUTCOME_RED if proc.returncode != 0 else OUTCOME_GREEN,
        returncode=proc.returncode, output=output)


def _snapshot(path: Path) -> str:
    """A digest of the artifact: its bytes, or every file under a scenario directory.

    Workflow-driven gates prepare a directory (a git history, a pytest project), so "did the
    mutation change anything" has to cover the tree rather than one file — a mutation that edited
    a file the criterion never reads would otherwise count as applied.
    """
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        digest = hashlib.sha256()
        for entry in sorted(path.rglob("*")):
            if entry.is_file() and not entry.is_symlink():
                digest.update(str(entry.relative_to(path)).encode("utf-8"))
                digest.update(hashlib.sha256(entry.read_bytes()).digest())
        return digest.hexdigest()
    raise OSError(f"{path} is neither a file nor a directory")


def run_audit(gates: Sequence[Gate] | None = None, *, online: bool = False,
              timeout: float = DEFAULT_TIMEOUT, verbose: bool = False) -> AuditReport:
    """Audit `gates` (default: the module-level `GATES` registry).

    A full run also checks that `GATES` covers every hard gate in `docs/ci-gates.md`; a `--gate`
    subset says nothing about coverage and does not pretend to. An unreadable document is an
    `AuditError` (exit 2) rather than a silent "everything is covered".
    """
    full_run = gates is None
    selected = list(gates) if gates is not None else list(GATES.values())
    hard = hard_gates() if full_run else None
    return AuditReport(
        [run_gate(gate, online=online, timeout=timeout, verbose=verbose) for gate in selected],
        hard_gates=hard)


def _preflight() -> str | None:
    """Reasons the audit cannot run at all."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return ("PyYAML is not installed, so the lesson gate cannot read YAML frontmatter and "
                "would fail for the wrong reason — run `python3 -m pip install -r requirements.txt`")
    return None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Internal entry point. The workflow-driven gates are judged in a child process of this same
    # file, so that what the audit observes is a real process exit status rather than an in-process
    # function call that could be mistaken for one.
    if argv[:1] == ["--_drive"]:
        if len(argv) != 3:
            print("internal: --_drive expects SPEC SCENARIO", file=sys.stderr)
            return EXIT_CANNOT_JUDGE
        return _drive(argv[1], Path(argv[2]))

    parser = argparse.ArgumentParser(
        prog="gate_mutation_audit.py",
        description="Can the gates still go red? Apply a mutation to each covered gate's input "
                    "in a temp directory and require the gate to fail (issue #2045, #3837).",
    )
    parser.add_argument("--gate", action="append", default=[], metavar="NAME",
                        help=f"audit only this gate (repeatable); known gates: {', '.join(GATES)}")
    parser.add_argument("--list-gates", action="store_true",
                        help="print the covered gates and the hard gate each one proves, then exit")
    parser.add_argument("--online", action="store_true",
                        help="also run mutations that need the network (default: skipped)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS",
                        help=f"per gate run (default: {DEFAULT_TIMEOUT:g})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print the full output of every gate run to stderr")
    args = parser.parse_args(argv)

    if args.list_gates:
        try:
            hard = hard_gates()
        except AuditError as exc:
            print(f"audit could not run: {exc}", file=sys.stderr)
            return 2
        covered = {gate.check for gate in GATES.values() if gate.check}
        for name, gate in GATES.items():
            label = gate.check or "not a hard gate"
            print(f"{name:<22} {label}")
        missing = [context for context in hard if context not in covered]
        print(f"\nhard gates from {_rel(HARD_GATES_DOC)}: {', '.join(hard)}")
        if missing:
            print(f"uncovered: {', '.join(missing)}")
            return 1
        return 0

    unknown = [name for name in args.gate if name not in GATES]
    if unknown:
        # Auditing nothing while exiting 0 is exactly the failure mode this script exists to
        # catch, so a typo must not be silent.
        print(f"unknown gate(s): {', '.join(unknown)} — nothing was audited. "
              f"Known gates: {', '.join(GATES)}", file=sys.stderr)
        return 2

    problem = _preflight()
    if problem:
        print(f"audit could not run: {problem}", file=sys.stderr)
        return 2

    selected = [GATES[name] for name in args.gate] if args.gate else None
    try:
        report = run_audit(selected, online=args.online, timeout=args.timeout, verbose=args.verbose)
    except AuditError as exc:
        print(f"audit could not run: {exc}", file=sys.stderr)
        return 2

    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
