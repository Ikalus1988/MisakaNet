#!/usr/bin/env python3
"""No job may run the test suite on a Python the suite cannot even be *collected* on.

Measured 2026-09-25: `.github/workflows/pr-checks.yml` — the "Misaka Network Agent Auditor", the
repository's real merge gate — pinned `python-version: "3.10"` while running the whole suite. Two test
files import `tomllib`, which is stdlib only from 3.11, so pytest died during **collection**
(`ModuleNotFoundError: No module named 'tomllib'`, exit 2) and the audit reported *"Audit failed: test
suite has issues"*. Every PR carried a red `audit`, including all the fork PRs waiting for review. The
required matrix had been 3.11/3.12/3.13 the whole time; the auditor was the outlier.

A failure that appears on every PR regardless of its content is not a gate, it is weather — and this
one had a single-line cause that nobody could see, because the auditor's summary blamed "the test
suite" rather than naming the version.

The floor is **derived, not declared**: `STDLIB_FLOORS` maps a stdlib module to the first Python that
ships it, and `suite_floor()` scans `tests/` for imports of those modules. Add `import tomllib` to a
new test and the floor moves by itself. That is the point — a hand-written "the suite needs 3.11" would
have been true today and stale the moment somebody reached for `except*`, `itertools.batched`, or
`datetime.UTC`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
TESTS = REPO / "tests"
MATRIX_WORKFLOW = WORKFLOWS / "ci-cross-platform.yml"

# stdlib module -> the first CPython release that ships it. Small and explicit on purpose: each entry
# is a claim about a version, and the test below refuses an entry that no test actually imports
# (a dead entry would only make the floor look stricter than it is).
STDLIB_FLOORS: dict[str, tuple[int, int]] = {
    "tomllib": (3, 11),          # 3.11+
}

Version = tuple[int, int]


def _v(text: str) -> Version:
    """`"3.10"` → `(3, 10)`. Parsed as integers: string comparison puts `"3.10" < "3.9"`, which would
    make the floor silently *lower* than intended on exactly the versions that matter here."""
    parts = re.findall(r"\d+", str(text))
    assert len(parts) >= 2, f"cannot read a major.minor version out of {text!r}"
    return (int(parts[0]), int(parts[1]))


def _imports(text: str) -> set[str]:
    found = set(re.findall(r"(?m)^\s*import\s+([a-zA-Z_][\w.]*)", text))
    found |= set(re.findall(r"(?m)^\s*from\s+([a-zA-Z_][\w.]*)\s+import", text))
    return {name.split(".")[0] for name in found}


def suite_floor() -> tuple[Version, list[str]]:
    """The lowest Python on which `pytest tests/` can reach collection, and the files that set it."""
    floor: Version = (0, 0)
    why: list[str] = []
    for path in sorted(TESTS.rglob("*.py")):
        for module in _imports(path.read_text(encoding="utf-8")) & set(STDLIB_FLOORS):
            if STDLIB_FLOORS[module] > floor:
                floor = STDLIB_FLOORS[module]
                why = [f"{path.name} imports {module}"]
            elif STDLIB_FLOORS[module] == floor:
                why.append(f"{path.name} imports {module}")
    return floor, why


def matrix_floor() -> tuple[Version, list[str]]:
    """The lowest version the required test matrix runs."""
    data = yaml.safe_load(MATRIX_WORKFLOW.read_text(encoding="utf-8"))
    versions: list[str] = []
    for job in (data.get("jobs") or {}).values():
        matrix = ((job.get("strategy") or {}).get("matrix") or {})
        raw = matrix.get("python-version")
        if isinstance(raw, list):
            versions += [str(v) for v in raw]
    assert versions, f"{MATRIX_WORKFLOW.name} has no python-version matrix to read"
    return min(_v(v) for v in versions), sorted(set(versions))


MATRIX_EXPR = re.compile(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}")


def _resolve_matrix(version: str, job: dict, where: str) -> list[str]:
    """Expand `python-version: ${{ matrix.python-version }}` into the job's real values.

    Not resolving it would drop the cross-platform matrix job out of the gate silently — and that is
    the job whose three versions are the definition of "tested" here, so a gate that cannot see it
    would pass anything. An expression that cannot be resolved raises rather than being skipped.
    """
    match = MATRIX_EXPR.fullmatch(str(version).strip())
    if not match:
        return [str(version)]
    matrix = ((job.get("strategy") or {}).get("matrix") or {})
    values = matrix.get(match.group(1))
    if not isinstance(values, list):
        raise ValueError(
            f"{where}: python-version is `{version}`, which comes from a matrix key that is not a "
            "plain list (only `include:`?) — this gate cannot read it, so it must not pretend to"
        )
    return [str(v) for v in values]


def pytest_jobs_pinning_python() -> list[tuple[str, str, str]]:
    """(workflow, job, version) for every job that runs pytest **and** pins a python-version.

    A job that runs pytest without `setup-python` uses the runner image's default, which is not in the
    file to check; those are listed by `jobs_running_pytest_without_pinning()` rather than silently
    passing.
    """
    out: list[tuple[str, str, str]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (data.get("jobs") or {}).items():
            steps = job.get("steps") or []
            runs_pytest = any("pytest" in (s.get("run") or "") for s in steps)
            if not runs_pytest:
                continue
            for step in steps:
                if not str(step.get("uses", "")).startswith("actions/setup-python"):
                    continue
                version = (step.get("with") or {}).get("python-version")
                if version:
                    for resolved in _resolve_matrix(version, job, f"{path.name}:{job_name}"):
                        out.append((path.name, job_name, resolved))
    return out


def jobs_running_pytest_without_pinning() -> list[str]:
    out = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (data.get("jobs") or {}).items():
            steps = job.get("steps") or []
            if not any("pytest" in (s.get("run") or "") for s in steps):
                continue
            if not any(str(s.get("uses", "")).startswith("actions/setup-python") for s in steps):
                out.append(f"{path.name}:{job_name}")
    return out


# ── the derivation has to work before anything it derives can be trusted ────────────
def test_the_floor_is_derived_and_has_a_reason():
    floor, why = suite_floor()
    assert floor > (0, 0), "no version-gated stdlib import found in tests/ — is the scanner broken?"
    assert why, "a floor without a file that sets it is a number, not a derivation"


def test_every_floor_entry_is_actually_used():
    """A dead entry would overstate the floor and fail jobs for no reason."""
    used: set[str] = set()
    for path in TESTS.rglob("*.py"):
        used |= _imports(path.read_text(encoding="utf-8"))
    for module in STDLIB_FLOORS:
        assert module in used, (
            f"STDLIB_FLOORS mentions {module!r} but no test imports it — delete the entry, or the "
            "floor is claiming a requirement the suite does not have"
        )


def test_versions_are_compared_as_numbers_not_strings():
    """The classic trap: as strings, `"3.10" < "3.9"` is True, so a string comparison would call 3.10
    *older* than 3.9 and let the exact pinning that caused this bug pass."""
    assert _v("3.10") > _v("3.9")
    assert _v("3.9") < _v("3.10")
    assert _v("3.11.5") == (3, 11)
    assert max(_v("3.9"), _v("3.10"), _v("3.11")) == (3, 11)


def test_the_gate_can_go_red():
    """The predicate, isolated: a 3.10 job against a 3.11 floor must be reported, not tolerated."""
    floor = (3, 11)
    offenders = [(wf, job, v) for wf, job, v in
                 [("pr-checks.yml", "audit", "3.10"), ("other.yml", "gate", "3.12")]
                 if _v(v) < floor]
    assert offenders == [("pr-checks.yml", "audit", "3.10")], offenders


def test_the_required_matrix_job_is_visible_to_this_gate():
    """The job that *defines* "tested" must not disappear from this gate's view.

    Its version is written as an expression (`${{ matrix.python-version }}`); a resolver that gave up
    on that would drop the job silently and every remaining assertion would still pass — including the
    one that compares against the matrix.
    """
    found = sorted(v for wf, _, v in pytest_jobs_pinning_python() if wf == MATRIX_WORKFLOW.name)
    _, matrix_versions = matrix_floor()
    assert found == matrix_versions, (
        f"this gate sees {found} for {MATRIX_WORKFLOW.name} but its matrix declares {matrix_versions}"
    )


# ── the rules ───────────────────────────────────────────────────────────────────────
def test_no_pytest_job_pins_a_python_below_the_suites_floor():
    floor, why = suite_floor()
    jobs = pytest_jobs_pinning_python()
    assert jobs, "no workflow job runs pytest with a pinned python-version — did the parser break?"
    offenders = [f"{wf}:{job} pins {v}" for wf, job, v in jobs if _v(v) < floor]
    assert offenders == [], (
        f"the test suite cannot be collected below {floor[0]}.{floor[1]} "
        f"({'; '.join(why)}), but these jobs run it there:\n  " + "\n  ".join(offenders)
        + "\nOn such a version pytest aborts during collection, so the job reports a red gate for "
          "every PR regardless of its content (measured 2026-09-25: pr-checks.yml pinned 3.10 and the "
          "auditor was red on every PR in the repository)."
    )


def test_the_required_matrix_can_collect_the_suite_it_gates():
    """If the matrix itself were below the floor, the *required* checks would abort during collection
    and no PR could ever be green."""
    floor, why = suite_floor()
    lowest, versions = matrix_floor()
    assert lowest >= floor, (
        f"{MATRIX_WORKFLOW.name} tests {versions}, but the suite needs >= "
        f"{floor[0]}.{floor[1]} ({'; '.join(why)})"
    )


@pytest.mark.parametrize("workflow", sorted({wf for wf, _, _ in pytest_jobs_pinning_python()}))
def test_the_auditor_does_not_run_the_suite_on_an_untested_version(workflow):
    """Where a job pins a version, it should pin one the repository actually tests: being *above* the
    floor is necessary but not sufficient — 3.13 is above the floor and still not what the required
    gate runs."""
    _, versions = matrix_floor()
    tested = {_v(v) for v in versions}
    jobs = [(job, _v(v)) for wf, job, v in pytest_jobs_pinning_python() if wf == workflow]
    untested = [f"{job} pins {v[0]}.{v[1]}" for job, v in jobs if v not in tested]
    assert untested == [], (
        f"{workflow} runs the suite on a version the matrix never tests: {untested}. Either add the "
        f"version to {MATRIX_WORKFLOW.name} (so it is supported on purpose) or pin a tested one."
    )
