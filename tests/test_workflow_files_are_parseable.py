#!/usr/bin/env python3
"""Two ways a workflow file is *valid YAML* and still cannot run.

GitHub's workflow parser is stricter than YAML, and when it refuses a file it does not run
the workflow and does not fail a job — it creates a **failed check suite with zero check
runs**. There is no job, no log and no annotation: the only trace is a banner on the run
page. A workflow in that state is invisible unless someone opens the run, which is why both
defects below survived undetected in this repository.

Measured 2026-10-15, both live on `main` at the same time:

* `provenance-gate.yml` — a comment documenting a removed line contained the literal
  expression `${{ ... }}`. GitHub substitutes `${{ }}` **even inside a YAML comment**, and
  `...` is not an expression, so the whole file was rejected:

      Invalid workflow file:
      (Line: 122, Col: 14): Unexpected symbol: '...'.

  That gate exists to check that a lesson's cited source actually resolves — it was written
  after four pull requests passed 24/24 checks while citing a repository that returns 404.
  Its last successful run was 2026-10-05; the Monday schedule after the break produced no run
  at all, because an unparseable workflow is never scheduled.

* `guarded-repository.yml` — a job that calls a reusable workflow (`uses:` at job level)
  carried `timeout-minutes`. GitHub rejects job-level keys it does not allow on a reusable
  workflow call:

      Invalid workflow file:
      Line: 44, Col: 5): Unexpected value 'timeout-minutes'

  `timeout-minutes` therefore belongs inside the called workflow, not on the call.

Neither file is in the ruleset's required checks, so neither failure blocked anything — which
is exactly why the class needs a test rather than attention.

The two checks are written as pure functions over `(name, text)` so each has a red fixture
below; a gate that has never been seen to fail is a gate nobody can trust.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# The token GitHub's expression parser looks for. It does not care that the line is a comment.
EXPRESSION_TOKEN = "${{"

# Keys GitHub rejects on a job whose `uses:` calls a reusable workflow. Taken from the
# documented job schema for `jobs.<job_id>` when `uses` is present: the only keys allowed are
# name/uses/with/secrets/strategy/needs/if/concurrency/permissions. Everything below is a
# normal-job key that looks plausible there and is refused.
ILLEGAL_ON_REUSABLE_CALL = frozenset({
    "timeout-minutes", "steps", "runs-on", "container", "services",
    "environment", "env", "defaults", "continue-on-error",
})


def comment_lines_with_an_expression(name: str, text: str) -> list[tuple[int, str]]:
    """Every comment line carrying the expression token, as (line number, line)."""
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("#") and EXPRESSION_TOKEN in line:
            found.append((lineno, line.strip()))
    return found


def illegal_job_keys(name: str, text: str) -> list[tuple[str, list[str]]]:
    """Every reusable-workflow call carrying a key GitHub refuses there."""
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        return []
    found = []
    for job_id, job in (parsed.get("jobs") or {}).items():
        if isinstance(job, dict) and "uses" in job:
            illegal = sorted(set(job) & ILLEGAL_ON_REUSABLE_CALL)
            if illegal:
                found.append((job_id, illegal))
    return found


def _workflow_files() -> list[Path]:
    return sorted(list(WORKFLOWS.glob("*.yml")) + list(WORKFLOWS.glob("*.yaml")))


def test_no_workflow_comment_carries_an_expression_token() -> None:
    """The `provenance-gate.yml` defect: a comment is not exempt from `${{ }}` parsing."""
    offenders = []
    for path in _workflow_files():
        for lineno, line in comment_lines_with_an_expression(path.name, path.read_text(encoding="utf-8")):
            offenders.append(f"  {path.name}:{lineno}: {line[:100]}")
    assert not offenders, (
        "These workflow comments contain the literal expression token `${{`, which GitHub's parser "
        "evaluates even inside a comment. If the text between the braces is not a valid expression "
        "the entire workflow file is refused, the workflow never runs, and the only symptom is a "
        "failed check suite with zero jobs:\n"
        + "\n".join(offenders)
        + "\nDescribe the expression in words, or use a placeholder like `<value>`, instead."
    )


def test_no_reusable_workflow_call_carries_a_job_only_key() -> None:
    """The `guarded-repository.yml` defect: `timeout-minutes` on a `uses:` job."""
    offenders = []
    for path in _workflow_files():
        for job_id, illegal in illegal_job_keys(path.name, path.read_text(encoding="utf-8")):
            offenders.append(f"  {path.name}: job '{job_id}' carries {illegal}")
    assert not offenders, (
        "A job that calls a reusable workflow (`uses:` at job level) accepts only "
        "name/uses/with/secrets/strategy/needs/if/concurrency/permissions. GitHub refuses the "
        "whole file for anything else, so the workflow never runs:\n"
        + "\n".join(offenders)
        + "\nMove the setting into the called workflow (the pin decides what runs) or out of that job."
    )


# ── Red fixtures: each check must be able to fail ─────────────────────────────────────────
# Static analysis is not enough here: the checks above read real files, so without these the
# only evidence they work is that they are green — which is what the two dead workflows also
# looked like. Each fixture is the exact shape that was measured on 2026-10-15.

def test_the_comment_check_can_go_red() -> None:
    text = (
        "jobs:\n"
        "  a:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: |\n"
        "          # This step could not fail. It was one line —\n"
        "          #   python3 scripts/check.py --strict ${{ ... }} | tee r.txt\n"
        "          echo ok\n"
    )
    found = comment_lines_with_an_expression("synthetic.yml", text)
    assert found, "the comment check did not notice the `${{ ... }}` that broke provenance-gate.yml"
    assert found[0][0] == 7


def test_the_comment_check_ignores_a_comment_without_the_token() -> None:
    text = "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      # no token here\n      - run: echo ok\n"
    assert comment_lines_with_an_expression("synthetic.yml", text) == []


def test_the_comment_check_ignores_the_token_in_real_script_text() -> None:
    """Only *comments* are checked — a `run:` body legitimately uses expressions."""
    text = (
        "jobs:\n"
        "  a:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo \"${{ github.sha }}\"\n"
    )
    assert comment_lines_with_an_expression("synthetic.yml", text) == []


def test_the_job_key_check_can_go_red() -> None:
    text = (
        "jobs:\n"
        "  guarded-repository:\n"
        "    uses: hashgraph-online/hol-guard/.github/workflows/guarded-repository.yml@abc123\n"
        "    timeout-minutes: 30\n"
        "    with:\n"
        "      profile: default\n"
    )
    found = illegal_job_keys("synthetic.yml", text)
    assert found, "the job-key check did not notice the `timeout-minutes` that broke guarded-repository.yml"
    assert found[0] == ("guarded-repository", ["timeout-minutes"])


def test_the_job_key_check_allows_the_keys_a_reusable_call_does_accept() -> None:
    text = (
        "jobs:\n"
        "  guarded-repository:\n"
        "    uses: owner/repo/.github/workflows/x.yml@abc123\n"
        "    permissions:\n"
        "      contents: read\n"
        "    strategy:\n"
        "      matrix:\n"
        "        python: ['3.11']\n"
        "    with:\n"
        "      profile: default\n"
        "    secrets: inherit\n"
    )
    assert illegal_job_keys("synthetic.yml", text) == []


def test_the_job_key_check_does_not_flag_a_normal_job() -> None:
    """`timeout-minutes` is legal on an ordinary job — the rule is about `uses:` jobs only."""
    text = (
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 30\n"
        "    steps:\n"
        "      - run: echo ok\n"
    )
    assert illegal_job_keys("synthetic.yml", text) == []


def test_every_workflow_file_parses_as_yaml() -> None:
    """A file that is not YAML at all is the crudest version of the same failure."""
    unparseable = []
    for path in _workflow_files():
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            unparseable.append(f"  {path.name}: {exc}")
    assert not unparseable, "these workflow files are not valid YAML:\n" + "\n".join(unparseable)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
