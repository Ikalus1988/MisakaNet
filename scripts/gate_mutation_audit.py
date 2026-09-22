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
For every gate in `GATES` it copies a *valid* artifact into a temporary directory (never the
repository tree), asserts the gate is green on it, then applies each **mutation** — a deliberate
break of the thing the gate is supposed to check — and asserts the gate exits non-zero.

The suspicious outcome is a **green** gate. If a gate stays green under its mutation, this script
prints `cannot fail` and exits non-zero; the same is true for a mutation that did not apply, a
baseline artifact that is already red, and a gate that hangs. "The gate went red" is the only
outcome counted as success.

Usage
-----
    python3 scripts/gate_mutation_audit.py                 # offline, every covered gate
    python3 scripts/gate_mutation_audit.py --gate lesson-gate
    python3 scripts/gate_mutation_audit.py --online        # also mutations that need the network
    python3 scripts/gate_mutation_audit.py -v              # full output of every gate run

Exit codes
----------
    0   every covered gate went red under every mutation that ran
    1   audit failed: a gate stayed green, or could not be judged (the interesting outcome)
    2   the audit could not run at all (unknown --gate, missing gate script, no PyYAML)

Covered gates, how to add one, how often it runs and who acts on a red result:
`docs/maintainer/gate-mutation-audit.md`. It runs **weekly on a schedule** and by manual
dispatch (`.github/workflows/gate-mutation-audit.yml`) — deliberately not on pull requests,
because mutation runs are slow and belong in a periodic audit, not in every PR's critical path.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

REPO = Path(__file__).resolve().parent.parent

LESSON_GATE = REPO / "scripts" / "lesson_gate.py"
PROVENANCE_GATE = REPO / "scripts" / "check_provenance.py"

DEFAULT_TIMEOUT = 120.0

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


def _mutate_dead_source(lesson: Path) -> None:
    """Cite a source that returns 404 — the case that motivated the gate.

    Offline this is unobservable by design (a network failure is `unknown`, never a failure), so
    the mutation is declared `network=True` and skipped unless `--online` is passed.
    """
    _sub(lesson, r"(?m)^source:[^\n]*$", f'source: "{DEAD_SOURCE_URL}"', "dead source")


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
    """A gate under audit, plus how to give it something valid to reject."""

    name: str
    description: str
    script: Path
    command: Callable[[Path, bool], list[str]]   # (lesson, online) -> argv
    mutations: tuple[Mutation, ...]
    prepare: Callable[[Path], Path]              # (run_dir) -> the valid artifact to copy


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
    argv = [sys.executable, str(PROVENANCE_GATE), "--check"]
    if not online:
        argv.append("--offline")
    argv.append(str(lesson))
    return argv


GATES: dict[str, Gate] = {
    "lesson-gate": Gate(
        name="lesson-gate",
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
    "provenance-gate": Gate(
        name="provenance-gate",
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

    @property
    def ok(self) -> bool:
        # An empty run is not a pass: "ran zero tests and printed ✅" is #2006/#2008, the very
        # failure mode this audit exists to catch, one level up.
        return bool(self.results) and all(result.ok for result in self.results)

    @property
    def failures(self) -> list[str]:
        if not self.results:
            return ["no gate was audited at all — auditing nothing is not a pass (#2006/#2008)"]
        return [line for result in self.results for line in result.failures()]

    def render(self) -> str:
        lines: list[str] = []
        for result in self.results:
            lines.append(f"# {result.gate.name} — {result.gate.description}")
            lines.append(f"  gate: {_rel(result.gate.script)}")
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
        lesson = Path(gate.prepare(run_dir))
    except Exception as exc:                       # noqa: BLE001 - reported, never raised
        return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                              detail=f"could not prepare the artifact: {exc}")

    if _inside_repo(lesson):
        return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                              detail=f"the artifact to mutate is inside the repository: {lesson}")

    if mutation is not None:
        before = lesson.read_bytes()
        try:
            mutation.apply(lesson)
        except Exception as exc:                   # noqa: BLE001 - a mutation that did not apply
            return MutationResult(mutation=mutation, outcome=OUTCOME_NOT_APPLIED,
                                  detail=f"{type(exc).__name__}: {exc}")
        if lesson.read_bytes() == before:
            return MutationResult(
                mutation=mutation, outcome=OUTCOME_NOT_APPLIED,
                detail="the mutation left the artifact byte-identical (a silent no-op)")
        if _inside_repo(lesson):
            return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                                  detail="the mutation moved the artifact into the repository: "
                                         f"{lesson}")

    argv = gate.command(lesson, online)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return MutationResult(mutation=mutation, outcome=OUTCOME_TIMEOUT, detail=f"{timeout:g}s")
    except OSError as exc:
        return MutationResult(mutation=mutation, outcome=OUTCOME_ERROR,
                              detail=f"could not run {argv[0]}: {exc}")

    output = (proc.stdout or "") + (proc.stderr or "")
    return MutationResult(
        mutation=mutation,
        outcome=OUTCOME_RED if proc.returncode != 0 else OUTCOME_GREEN,
        returncode=proc.returncode, output=output)


def run_audit(gates: Sequence[Gate] | None = None, *, online: bool = False,
              timeout: float = DEFAULT_TIMEOUT, verbose: bool = False) -> AuditReport:
    """Audit `gates` (default: the module-level `GATES` registry)."""
    selected = list(gates) if gates is not None else list(GATES.values())
    return AuditReport([run_gate(gate, online=online, timeout=timeout, verbose=verbose)
                        for gate in selected])


def _preflight() -> str | None:
    """Reasons the audit cannot run at all."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return ("PyYAML is not installed, so the lesson gate cannot read YAML frontmatter and "
                "would fail for the wrong reason — run `python3 -m pip install -r requirements.txt`")
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gate_mutation_audit.py",
        description="Can the gates still go red? Apply a mutation to each covered gate's input "
                    "in a temp directory and require the gate to fail (issue #2045).",
    )
    parser.add_argument("--gate", action="append", default=[], metavar="NAME",
                        help=f"audit only this gate (repeatable); known gates: {', '.join(GATES)}")
    parser.add_argument("--online", action="store_true",
                        help="also run mutations that need the network (default: skipped)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS",
                        help=f"per gate run (default: {DEFAULT_TIMEOUT:g})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print the full output of every gate run to stderr")
    args = parser.parse_args(argv)

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

    selected = [GATES[name] for name in args.gate] if args.gate else list(GATES.values())
    try:
        report = run_audit(selected, online=args.online, timeout=args.timeout, verbose=args.verbose)
    except AuditError as exc:
        print(f"audit could not run: {exc}", file=sys.stderr)
        return 2

    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
