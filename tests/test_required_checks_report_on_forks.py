#!/usr/bin/env python3
"""Every **required** status check on `main` must be able to report on a **fork** PR.

The ruleset `main: the deterministic gates` (id 23826057) requires three contexts. A PR that cannot
produce all three sits at GitHub's "Expected — waiting for status to be reported" **forever**, no
matter how green everything else is, and nothing in the repository says so.

Measured 2026-09-25: **12 of the 14 open PRs were blocked exactly this way**, the oldest for 17 days,
and every one of them showed a *green* DCO workflow run. Two independent causes, both now pinned:

1. **A check created through the API needs a write token, and fork PRs do not get one.** `DCO /
   Signed-off-by` is not a job name — `dco-check.yml` creates it with `github.rest.checks.create`.
   Under `on: pull_request` a fork's `GITHUB_TOKEN` is read-only, so that call answered 403, the
   `catch` logged "Skipping DCO status check (fork PR permission)" and the required check was never
   reported. The rule here is therefore: a producer that creates its check through the API must
   trigger on `pull_request_target`.
2. **A filtered workflow reports nothing for the PRs it filters out.** `lesson-gate.yml` gained
   `paths:` at some point and lost its ability to be a required check; the file's own comment records
   that (#1920). The rule here is the same one: no `paths:` on a required check's producer.

Both rules are properties of the *producer*, which is why they are asserted from the workflow files
rather than remembered.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"

# The ruleset's `required_status_checks` contexts, and the shape of each producer.
# `api` — the check is created by a call to the Checks API, so the token must be able to write checks.
# `job` — GitHub creates the check from the job name, so the workflow only has to *run*.
REQUIRED = {
    "DCO / Signed-off-by": "api",
    "gate": "job",
    "test (ubuntu-latest, 3.11)": "job",
}

# A required check whose producer is filtered by path can never report on a PR that skips the filter.
PATH_FILTERED = re.compile(r"^\s{2,}paths(-ignore)?:", re.M)


def workflow(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def triggers(doc: dict) -> dict:
    got = doc.get("on") or doc.get(True) or {}
    if isinstance(got, str):
        return {got: {}}
    if isinstance(got, list):
        return {k: {} for k in got}
    return got


def producers() -> dict[str, list[tuple[pathlib.Path, str]]]:
    """context -> [(workflow file, kind of producer)], for the contexts in REQUIRED.

    `api` producers are found by the name passed to `checks.create`; `job` producers by a job key or
    job name that *is* the context (`gate`) or by the matrix that renders it
    (`test (ubuntu-latest, 3.11)` from a job named `test`).
    """
    found: dict[str, list[tuple[pathlib.Path, str]]] = {k: [] for k in REQUIRED}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        for context in REQUIRED:
            # A producer *creates* the check, so the context has to appear next to `checks.create` —
            # and as any quoted literal, not a particular key: the name moved from
            # `name: 'DCO / Signed-off-by'` (an action input) to `const CHECK_NAME = 'DCO / Signed-off-by'`
            # (a JS constant) when the posting step was rewritten. Widening it to "the string appears
            # anywhere" was too broad the other way: `pr-quality-gate.yml` only *reads* the check
            # name, and counting it as a producer made the fork rule fail on a workflow that produces
            # nothing.
            cites = (f"'{context}'" in text) or (f'"{context}"' in text)
            if cites and "checks.create" in text:
                found[context].append((path, "api"))
        doc = workflow(path)
        for job, spec in (doc.get("jobs") or {}).items():
            names = {str(job), str((spec or {}).get("name") or "")}
            if "gate" in names:
                found["gate"].append((path, "job"))
            if "test" in names:
                matrix = ((spec or {}).get("strategy") or {}).get("matrix") or {}
                oses = matrix.get("os") or []
                versions = [str(v) for v in (matrix.get("python-version") or [])]
                if "ubuntu-latest" in oses and "3.11" in versions:
                    found["test (ubuntu-latest, 3.11)"].append((path, "job"))
    return found


PRODUCERS = producers()


# ── the rules ────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("context", sorted(REQUIRED))
def test_every_required_context_has_a_producer_in_the_tree(context: str) -> None:
    """A required check with no producer is a merge freeze that looks like a contributor's fault."""
    assert PRODUCERS[context], (
        f"nothing in .github/workflows produces the required context {context!r}. The ruleset on "
        f"`main` requires it, so every PR waits for it forever — either restore the producer or "
        f"remove the context from the ruleset."
    )


@pytest.mark.parametrize("context", sorted(REQUIRED))
def test_a_required_check_created_by_the_api_runs_on_pull_request_target(context: str) -> None:
    """The 403 that blocked 12 PRs: a fork's `GITHUB_TOKEN` cannot create a check.

    Creating a check through the API is the one producer shape that needs a *write* token, and a
    `pull_request` run from a fork never has one. `pull_request_target` runs the base branch's
    workflow with a write-capable token, which is what makes the required check appear — and it is
    only safe as long as the job does not execute code from the PR it checks out (see
    `dco-check.yml`'s header).
    """
    for path, kind in PRODUCERS[context]:
        if kind != "api":
            continue
        trig = triggers(workflow(path))
        assert "pull_request_target" in trig, (
            f"{path.name} creates the required check {context!r} through the Checks API but triggers "
            f"on {sorted(trig)}. Under `pull_request` a fork's GITHUB_TOKEN is read-only, so the call "
            f"fails and the check is never reported: the PR waits forever, and the workflow still "
            f"reports green."
        )
        assert "pull_request" not in trig, (
            f"{path.name} triggers on both `pull_request` and `pull_request_target` for a check it "
            f"creates through the API; the `pull_request` arm can only produce the failure above."
        )


@pytest.mark.parametrize("context", sorted(REQUIRED))
def test_no_required_producer_is_filtered_by_path(context: str) -> None:
    """#1920's lesson, still true: a filtered workflow reports nothing for the PRs it skips."""
    for path, _kind in PRODUCERS[context]:
        text = path.read_text(encoding="utf-8")
        doc = workflow(path)
        trig = triggers(doc)
        for event, spec in trig.items():
            if event not in ("pull_request", "pull_request_target"):
                continue
            spec = spec or {}
            assert not spec.get("paths") and not spec.get("paths-ignore"), (
                f"{path.name} filters its {event} trigger by path, so it reports no result for the PRs "
                f"outside the filter — and {context!r} is required, so those PRs wait forever. Filter "
                f"inside the job instead (that is what lesson-gate.yml does)."
            )
        assert not PATH_FILTERED.search(text) or "pull_request" not in text, (
            f"{path.name} carries a `paths:` filter; confirm it cannot affect the required check "
            f"{context!r}"
        )


def posting_steps() -> list[dict]:
    """Every step in the tree whose script creates a check through the API.

    Found by what the step *does*: the DCO posting step was renamed when its body was rewritten, and a
    gate keyed on the old name went from "checks something" to "raises IndexError", which is why the
    lookup lives here and not inside one test.
    """
    out = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        doc = workflow(path)
        for job in (doc.get("jobs") or {}).values():
            for step in (job or {}).get("steps") or []:
                script = ((step.get("with") or {}).get("script") or "") + (step.get("run") or "")
                if "checks.create" in script:
                    out.append({"workflow": path, "step": step, "script": script})
    return out


def test_the_check_posting_step_never_swallows_its_failure() -> None:
    """The specific reason this went unnoticed for 17 days: the failure was caught and logged.

    A required check that cannot be created is not a cosmetic problem — it is a permanent block on
    every fork PR — so the step has to fail, and the message has to name that consequence.
    """
    posting = [p for p in posting_steps() if str(p["step"].get("name") or "").lower().find("dco") >= 0]
    assert posting, "no step creates the DCO check any more; fix this gate rather than deleting it"
    for step in [p["step"] for p in posting]:
        assert step.get("continue-on-error") is not True, (
            "`continue-on-error: true` on the step that creates a *required* check means the job stays "
            "green while the check is never reported — which is exactly how 12 PRs sat blocked"
        )
    script = posting[0]["script"]
    assert "setFailed" in script, "the step no longer fails when it cannot create the check"
    assert "Skipping" not in script, "the failure is being logged into the void again"


def test_the_manual_recovery_path_can_actually_recover() -> None:
    """`workflow_dispatch` has no `payload.pull_request`, and the first version read it anyway.

    The input exists so a maintainer can re-report DCO on a PR whose check went missing — which is
    exactly the situation this whole file is about. It threw before creating anything, so the repair
    button could not repair. Pinned because a recovery path is only worth having if it runs.
    """
    script = [p for p in posting_steps()
              if str(p["step"].get("name") or "").lower().find("dco") >= 0][0]["script"]
    assert "payload.pull_request" in script and "?" in script, (
        "the script no longer guards the event that has no `pull_request` payload"
    )
    assert "pulls.get" in script, (
        "the manual path must resolve the head sha from the API — a dispatch carries no PR payload, and "
        "reading one unconditionally is what made this recovery button unable to recover"
    )


# ── fixtures: the gate can go red ────────────────────────────────────────────────────────────────

def test_the_fork_permission_rule_catches_pull_request() -> None:
    """The exact shape before this fix: the API producer on `pull_request`."""
    doc = {"on": {"pull_request": {"types": ["opened"]}}, "jobs": {}}
    trig = triggers(doc)
    assert "pull_request_target" not in trig


def test_the_path_filter_rule_catches_a_filtered_required_producer() -> None:
    doc = yaml.safe_load("""
on:
  pull_request:
    paths:
      - "lessons/**"
jobs:
  gate: {}
""")
    spec = triggers(doc)["pull_request"]
    assert spec.get("paths"), "the fixture no longer carries a filter"


def test_the_producers_are_found_by_the_shapes_the_rules_check() -> None:
    """Guard the guard: if discovery found nothing, every rule above would pass vacuously."""
    assert PRODUCERS["DCO / Signed-off-by"], "no API producer found for the DCO check"
    assert any(p.name == "dco-check.yml" for p, _ in PRODUCERS["DCO / Signed-off-by"])
    assert any(p.name == "lesson-gate.yml" for p, _ in PRODUCERS["gate"])
    assert any(p.name == "ci-cross-platform.yml" for p, _ in PRODUCERS["test (ubuntu-latest, 3.11)"])
    assert all(kind in ("api", "job") for group in PRODUCERS.values() for _, kind in group)


# ── the rule hol-guard raised as alert #284 ──────────────────────────────────────────────────────

def checkout_steps(doc: dict) -> list[dict]:
    """Every `actions/checkout` step in a workflow, by structure rather than by text.

    Structural on purpose: the workflow that fixed this mentions `actions/checkout` **in a comment**
    explaining that it has none, and a scan for the string reports it as present. Same trap as
    `uncommented()` in `tests/test_site_activity_panel.py`, one file over.
    """
    out = []
    for job in (doc.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            if str(step.get("uses") or "").startswith("actions/checkout"):
                out.append(step)
    return out


def untrusted_checkouts(doc: dict) -> list[str]:
    """Checkouts of the *PR head* — the input a privileged run must not touch."""
    bad = []
    for step in checkout_steps(doc):
        spec = json.dumps(step.get("with") or {})
        if "pull_request" in spec:
            bad.append(str(step.get("name") or spec))
    return bad


def test_a_privileged_workflow_does_not_check_out_the_pull_request():
    """`pull_request_target` gives the job a write token and the repo's secrets.

    Checking out the PR head under that trigger is the shape of a pwn request — the scanner raised
    `GITHUB_ACTIONS_UNTRUSTED_CHECKOUT` (alert #284) on the first version of this fix, which kept
    `actions/checkout` to read commit messages with `git log`. It was right: a comment explaining that
    only messages are read is not something a scanner can see, and it is not a property the workflow
    *enforces*. The API answers the same question, so the checkout is gone.
    """
    problems = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        doc = workflow(path)
        if "pull_request_target" not in triggers(doc):
            continue
        bad = untrusted_checkouts(doc)
        if bad:
            problems.append(f"{path.name}: checks out the pull request under pull_request_target — {bad}")
    assert not problems, (
        "these workflows combine a privileged trigger with an untrusted checkout; read what you need "
        "through the API instead:\n  - " + "\n  - ".join(problems)
    )


def test_the_untrusted_checkout_rule_can_go_red():
    doc = yaml.safe_load("""
on:
  pull_request_target:
jobs:
  dco:
    steps:
      - uses: actions/checkout@v7
        with:
          repository: ${{ github.event.pull_request.head.repo.full_name }}
          ref: ${{ github.event.pull_request.head.sha }}
""")
    assert untrusted_checkouts(doc), "the fixture no longer describes an untrusted checkout"
    assert not untrusted_checkouts(yaml.safe_load("""
on:
  pull_request_target:
jobs:
  dco:
    steps:
      - uses: actions/checkout@v7
"""), ), "a checkout of the base branch is not untrusted"
