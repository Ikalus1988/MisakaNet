#!/usr/bin/env python3
"""A document that tells you to run the test suite must state the version the *suite* needs.

`pyproject.toml` declares `requires-python = ">=3.10"` and the ruff target is `py310` — both true of the
**library**. The **suite** needs 3.11+, because `tests/` imports `tomllib`, which is stdlib only from 3.11. So
a contributor on 3.10 could follow the environment line in `docs/agents/repo-operations.md` ("Python ≥ 3.10"),
`pip install -r requirements.txt` successfully, and then watch `pytest tests/` exit during **collection** with
`ModuleNotFoundError: No module named 'tomllib'` — a message that reads like a broken checkout rather than a
version floor. That is the same failure `pr-checks.yml` had (measured 2026-09-25: the auditor pinned 3.10 and
every PR carried a red auditor while blaming "the test suite").

Two rules, and they are about the *relation* rather than a number:

* a document that names a Python floor **and** tells the reader to run the suite must also name the suite's
  floor — which is **derived** by `tests/test_workflow_python_floors.py`, so the number cannot drift away from
  CI;
* no document may pair a *lower* version with a suite instruction (a stale "Python 3.9+" next to
  `pytest tests/` is worse than no number at all).

`README.md` states a floor for *using* the library and never tells anyone to run the suite, so it is left
alone — the rule is deliberately about the combination.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

# The documents a contributor reads before their first test run. Discovered by glob, so a new one is covered.
DOCS = [REPO / "README.md", REPO / "CONTRIBUTING.md"] + sorted((REPO / "docs" / "agents").glob("*.md"))

FLOOR_CLAIM = re.compile(r"[Pp]ython\s*(?:≥|>=|>|3\.\d+\+|\s*3\.\d+\s*\+)")
VERSION = re.compile(r"3\.(\d+)")
RUNS_SUITE = re.compile(r"pytest|tests/", re.I)
POINTER = "test_workflow_python_floors"


def suite_floor() -> tuple[int, int, list[str]]:
    """The suite's floor, from the same derivation CI is held to."""
    import test_workflow_python_floors as floors

    floor, why = floors.suite_floor()
    return floor[0], floor[1], why


def floor_problems(docs: dict[str, str], floor: tuple[int, int] = (3, 11)) -> list[str]:
    """Documents that state a floor for the suite, or state one below it."""
    problems = []
    for name, text in docs.items():
        claims_floor = FLOOR_CLAIM.search(text) is not None
        if not claims_floor or not RUNS_SUITE.search(text):
            continue
        named = {(3, int(minor)) for minor in VERSION.findall(text)}
        # The suite's floor (or higher) must be named…
        if not any(v >= floor for v in named):
            problems.append(
                f"{name} names a Python floor and tells the reader to run the suite, but never names "
                f"{floor[0]}.{floor[1]} — the suite imports `tomllib`, so on {min(named or [(3, 10)])[0]}."
                f"{min(named or [(3, 10)])[1]} pytest exits during collection and nothing runs")
        # …and the derivation must be pointed at, so the number cannot drift from CI.
        if POINTER not in text:
            problems.append(
                f"{name} states a floor without pointing at `{POINTER}`, which derives it — a hand-written "
                "number is how the two floors drifted apart in the first place")
    return problems


def _docs() -> dict[str, str]:
    return {p.relative_to(REPO).as_posix(): p.read_text(encoding="utf-8") for p in DOCS if p.is_file()}


def test_the_documents_that_run_the_suite_state_the_suites_floor():
    major, minor, why = suite_floor()
    problems = floor_problems(_docs(), (major, minor))
    assert not problems, (f"the suite's floor is {major}.{minor} (derived from {', '.join(why)}):\n  - "
                          + "\n  - ".join(problems))


def test_the_rule_catches_a_document_that_only_names_the_library_floor():
    """Replayed on the state `docs/agents/repo-operations.md` was in: one floor, dated 3.10."""
    fixture = {"x.md": "Working here\n\n- **Python ≥ 3.10**\n\n```bash\npytest tests/ -v\n```\n"}
    problems = floor_problems(fixture)
    assert len(problems) == 2, problems
    assert "3.11" in problems[0] and POINTER in problems[1], problems


def test_the_rule_ignores_a_document_that_only_uses_the_library():
    """`README.md`'s prerequisites answer "can I use this?", not "can I run the tests?"."""
    fixture = {"x.md": "**Prerequisites:** Python ≥ 3.10 for the library.\n"}
    assert floor_problems(fixture) == []


def test_the_rule_accepts_a_document_that_names_both():
    fixture = {"x.md": "Python ≥ 3.10 for the library; **the test suite needs 3.11+** "
                       "(`tests/test_workflow_python_floors.py` derives it).\n\npytest tests/\n"}
    assert floor_problems(fixture) == []


def test_the_derivation_is_the_one_that_exists():
    """Guard: if the deriving test is renamed, this rule would be checking a number nobody derives."""
    assert (REPO / "tests" / f"{POINTER}.py").is_file(), f"tests/{POINTER}.py is gone"
    major, minor, why = suite_floor()
    assert (major, minor) >= (3, 10) and why, (major, minor, why)


def test_the_documents_are_the_real_ones():
    docs = _docs()
    assert "CONTRIBUTING.md" in docs and "docs/agents/repo-operations.md" in docs, sorted(docs)
    assert len(docs) > 5, sorted(docs)
