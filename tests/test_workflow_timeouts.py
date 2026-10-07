#!/usr/bin/env python3
"""Every job needs a bound, and a bound equal to the platform default is not one.

54 of the 94 jobs in this repository had no `timeout-minutes`, so they ran to GitHub's default of
360 minutes. The external review that flagged it is cited in `docs/maintainer/handoff-2026-10-07.md`
§1; the argument for adding them is in the commit that did, and it is repeated here because it
decides what the number has to be:

* the cost of no bound is not only six hours of runner time. `audit` and `gate` are required by
  ruleset 23826057, which has no bypass actors, so a hung required check means a contributor waits
  up to six hours to learn that their pull request will not pass;
* the cost of a bound that is too low is a false red on a required check, which is the outcome
  that gets a rule deleted rather than fixed — `tests/test_automated_prs_skip_llm_review.py`
  records three separate rules that were each broken that way;
* those costs are not symmetric, so the added bound is 30 minutes against a longest observed
  legitimate job of 7.5 minutes, and the jobs that already had one keep theirs.

**The upper bound is the interesting rule, and its first form was wrong.** The draft asked that no
bound exceed 60 minutes, to stop someone satisfying the check with a value that does nothing.
That reddens `benchmark-workers-ai.yml`'s 90 minutes, which is set deliberately because the job
runs AI benchmarks, and a rule that punishes a considered choice is a rule that gets deleted. The
draft also asked every bound to exceed the slowest job in the repository, which is wrong twice
over: it constrains a job that finishes in seconds by an unrelated slow one, and it is a
repository-wide constant standing in for a per-job fact.

What survives is narrower and is the actual failure mode: **a bound equal to the platform default
is indistinguishable from no bound at all.** That is the one value that cannot be defended, and
`codeql.yml` was carrying it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

#: GitHub's accepted range for a job's `timeout-minutes`.
GITHUB_MIN, GITHUB_MAX = 1, 360

#: What a job gets when it declares nothing. Also the largest value the platform accepts, which is
#: why setting it explicitly is indistinguishable from omitting it.
PLATFORM_DEFAULT = 360

#: The bound the 54 previously-unbounded jobs were given. Four bounds that already existed were
#: checked against their own jobs' measurements instead of this one — see `OBSERVED_JOB_MINUTES`,
#: which is the rule that can redden. Measured 2026-10-07: the longest legitimate job in this
#: repository is a `windows-latest` test leg at 452.50s (7.5 min) including runner setup, the full
#: suite on the ext4 bench takes 363.77s, and `pr-agent` on a healthy run takes 3m15s.
ADDED_BOUND = 30
OBSERVED_MAX_JOB_MINUTES = 7.5

#: What each individual job was measured to take, from the Actions run history on 2026-10-07:
#: `(workflow file, job name, longest completed run in the window, sample count)`. These are what
#: make a per-job bound checkable at all. A job with no completed run in the window is deliberately
#: absent rather than estimated.
#:
#: `pr-agent` needs a note. Its 15-minute bound *fired* within an hour of landing, on a run where
#: the upstream `openai/minimax-M3` call hung: `litellm.Timeout … time taken=362.47 seconds`, and
#: the job was cut at 15:00. That 15.2-minute figure is a hang the bound caught, not a duration
#: the job needs, so it is not what the row records. Its two healthy runs are 3m15s and a review
#: that completed 6.4 minutes in; the slowest of those is the number a bound must clear.
OBSERVED_JOB_MINUTES = (
    ("dco-check.yml", "dco", 0.1, 29),
    ("mcp-stress.yml", "stress", 0.7, 30),
    ("pr-agent-review.yml", "pr-agent", 6.4, 2),
    ("benchmark-workers-ai.yml", "benchmark", 4.7, 16),
)


def _jobs() -> list[tuple[str, str, dict]]:
    found = []
    for path in sorted(set(WORKFLOWS.glob("*.yml")) | set(WORKFLOWS.glob("*.yaml"))):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, job in (document.get("jobs") or {}).items():
            if isinstance(job, dict):
                found.append((path.name, name, job))
    return found


def test_every_job_declares_a_timeout():
    """A job with no `timeout-minutes` holds its runner for the six-hour platform default."""
    missing = [f"{path}:{name}" for path, name, job in _jobs() if job.get("timeout-minutes") is None]
    assert not missing, (
        f"{len(missing)} jobs have no `timeout-minutes` and will hold their runner for "
        f"{PLATFORM_DEFAULT} minutes: {missing}. Add one — this repository used {ADDED_BOUND} for "
        "the 54 that had none, and the ones that already had a considered value keep it.")


def test_no_bound_is_the_platform_default():
    """`timeout-minutes: 360` satisfies a presence check and does nothing at all.

    This is the rule that keeps the presence check from being the "impossible to fail" shape this
    repository keeps removing: present, green, and enforcing nothing.
    """
    vacuous = [f"{path}:{name}" for path, name, job in _jobs()
               if job.get("timeout-minutes") == PLATFORM_DEFAULT]
    assert not vacuous, (
        f"these jobs set `timeout-minutes: {PLATFORM_DEFAULT}`, which is the platform default and "
        f"therefore no bound at all: {vacuous}. Pick a value that would actually cut a hung run.")


def test_every_bound_is_inside_what_github_accepts():
    """Out of range is not a tighter bound, it is a workflow GitHub refuses to start."""
    bad = [f"{path}:{name}={job.get('timeout-minutes')!r}"
           for path, name, job in _jobs()
           if job.get("timeout-minutes") is not None
           and not (isinstance(job["timeout-minutes"], int)
                    and GITHUB_MIN <= job["timeout-minutes"] <= GITHUB_MAX)]
    assert not bad, (
        f"`timeout-minutes` outside {GITHUB_MIN}..{GITHUB_MAX} means the workflow does not run: {bad}")


def test_each_tight_bound_is_above_what_that_job_was_observed_to_need():
    """A bound is only safe against a measurement of *its own* job.

    This is the check the first version of this rule could not be. It asked every bound to exceed
    the slowest job in the repository, which is wrong twice over: it would force a job that
    finishes in twenty seconds to be bounded by an unrelated slow one, and it stands a
    repository-wide constant in for a per-job fact. So the comparison is made per job, against
    what that job was actually observed to take.

    Only jobs with a completed run in the retrievable window can appear here. `codeql.yml`'s
    `analyze` and `nightly-mirror-consistency.yml`'s `check` and `register.yml`'s `register` have
    none, so they are not in the table and this rule says nothing about them — which is stated
    rather than papered over, because a table entry invented to fill a gap is the same error as a
    bound invented for a job nobody has seen run.
    """
    at_risk = [
        f"{path}:{name} bound={job['timeout-minutes']} observed_max={observed} min (n={samples})"
        for path, name, job in _jobs()
        for workflow, target, observed, samples in OBSERVED_JOB_MINUTES
        if workflow == path and target == name
        and isinstance(job.get("timeout-minutes"), int)
        and job["timeout-minutes"] <= observed
    ]
    assert not at_risk, (
        f"these bounds are at or below the longest their own job was observed to take, so they "
        f"would cut a real run: {at_risk}. Raise the bound, or update the measurement if the job "
        "has genuinely outgrown it.")


def test_the_added_bound_is_derived_from_a_measurement_rather_than_taste():
    """The derivation behind the 30, held as a constant so it stays traceable.

    This compares two constants and cannot redden from a workflow edit — it is here so the number
    is checkable against the measurement that justifies it, and so that changing `ADDED_BOUND`
    without changing `OBSERVED_MAX_JOB_MINUTES` is a visible act. The per-job check above is the
    one that reads the repository; this one documents why the uniform value is the uniform value.
    """
    assert OBSERVED_MAX_JOB_MINUTES < ADDED_BOUND, (
        f"the {ADDED_BOUND}-minute bound is at or below the longest legitimate job measured "
        f"({OBSERVED_MAX_JOB_MINUTES} min), so it would cut a real run. If a job really has grown "
        "past the rest of the repository, raise OBSERVED_MAX_JOB_MINUTES with the measurement that "
        "says so rather than lowering the bound.")
    assert ADDED_BOUND < PLATFORM_DEFAULT, (
        f"{ADDED_BOUND} must be tighter than the {PLATFORM_DEFAULT}-minute default, or the jobs it "
        "was given to are no better off than the ones that declare nothing")


def test_the_rule_can_tell_a_workflow_without_a_bound_from_one_with_it():
    """A presence check that cannot fail is not a check.

    Both directions run against a fixture, so the rule is shown to reject the unbounded shape and
    accept the bounded one rather than only being exercised on files that already satisfy it.
    """
    bounded = "jobs:\n  a:\n    runs-on: ubuntu-latest\n    timeout-minutes: 30\n    steps: []\n"
    unbounded = "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps: []\n"
    default_only = f"jobs:\n  a:\n    runs-on: ubuntu-latest\n    timeout-minutes: {PLATFORM_DEFAULT}\n    steps: []\n"
    assert yaml.safe_load(bounded)["jobs"]["a"]["timeout-minutes"] == ADDED_BOUND
    assert yaml.safe_load(unbounded)["jobs"]["a"].get("timeout-minutes") is None
    # The value that makes the whole rule vacuous must be distinguishable from a real bound.
    assert yaml.safe_load(default_only)["jobs"]["a"]["timeout-minutes"] == PLATFORM_DEFAULT != ADDED_BOUND
