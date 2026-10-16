#!/usr/bin/env python3
"""A workflow that opens a pull request must do it as the PAT, not as `GITHUB_TOKEN`.

Measured 2026-10-17, same repository, same hour:

| PR | pushed / opened by | runs on the new head |
|---|---|---|
| #3366 (`/adopt` of #3344) | `github-actions[bot]` (`GITHUB_TOKEN`) | 14 `pull_request` runs, **all `action_required` at 0s**; only the Cloudflare check-run reported |
| #3362 (`bot/build-feed`) | `Ikalus1988` (`SHELDON_PAT`) | 22 checks, all normal |

GitHub creates a `GITHUB_TOKEN`-authored branch's `pull_request` runs **held**
(`conclusion: action_required`, no job starts), so the PR collects no required check and can never
merge — while every log says the workflow succeeded.

The mechanism is already documented three times (`fix-dco.yml:156`, `build-feed.yml:139`,
`auto-sync-prs.yml:73`) and pinned for `land_change.py` landers by
`tests/test_landers_push_as_the_pat.py`. That guard discovers its subjects **by the lander script**,
so it cannot see either of the two workflows that open a PR by hand: `adopt-pr.yml` (which pushed
`adopted/<n>` itself) and `auto-draft.yml`. Both were outside every rule; the first one stranded its
PR today.

The rule here is discovered the same way, by the operation that causes the harm: any step that runs
`gh pr create` is covered, so the next PR-opening workflow inherits it.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
PAT = "secrets.SHELDON_PAT"

#: `auto-draft.yml` opens its PR with `GITHUB_TOKEN` and additionally has two independent reasons it
#: could not land even with the PAT: its commit message is `[skip ci]` (so the runs are skipped
#: rather than held) and it carries no `Signed-off-by:` trailer (DCO is a required check). Fixing
#: only the token would move the red from "no checks ran" to "DCO failed" — the mistake the handoff
#: records as §99.2. Listed here *with the reason* so the debt is visible rather than silent.
EXEMPT = {"auto-draft.yml"}


def pr_opening_steps():
    """(workflow name, job name, step, job env) for every step whose `run:` calls `gh pr create`."""
    for path in WORKFLOWS:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (data.get("jobs") or {}).items():
            for step in (job.get("steps") or []):
                run = str(step.get("run") or "")
                # A mention in a shell comment is not a call (the lander guard learned this the hard
                # way); compare line by line with the comments removed.
                if any("gh pr create" in line for line in run.splitlines()
                       if not line.lstrip().startswith("#")):
                    yield path.name, job_name, step, (job.get("env") or {})


def token_problems(items) -> list[str]:
    problems = []
    for name, job_name, step, job_env in items:
        if name in EXEMPT:
            continue
        merged = {**(job_env or {}), **((step.get("env") or {}))}
        token = str(merged.get("GH_TOKEN") or merged.get("GITHUB_TOKEN") or "")
        if PAT not in token:
            problems.append(
                f"{name}:{job_name}:{step.get('name', '(unnamed step)')} opens a pull request with "
                f"{token or 'no GH_TOKEN'} — the push is attributed to `github-actions[bot]`, its runs "
                f"are created held, and no required check can ever report")
    return problems


def test_every_pr_opening_workflow_pushes_as_the_pat():
    items = list(pr_opening_steps())
    assert len(items) >= 2, f"only found {[(i[0], i[1]) for i in items]} — the discovery is broken"
    assert token_problems(items) == [], "\n  - " + "\n  - ".join(token_problems(items))


def test_the_rule_can_go_red():
    """Replayed on the state `adopt-pr.yml` was in before this fix (and that `auto-draft.yml` is in)."""
    fixture = [("x.yml", "job",
                {"name": "open", "run": "gh pr create --base main --head bot/x",
                 "env": {"GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}}, {})]
    problems = token_problems(fixture)
    assert len(problems) == 1 and "held" in problems[0], problems
    fixture[0][2]["env"]["GH_TOKEN"] = "${{ secrets.SHELDON_PAT || secrets.GITHUB_TOKEN }}"
    assert token_problems(fixture) == []


def test_a_comment_is_not_a_call():
    """`gh pr create` inside a shell comment must not pull a workflow into the rule."""
    commented = [("y.yml", "job", {"name": "explain", "run": "# gh pr create --base main"}, {})]
    assert token_problems([i for i in commented if _is_call(i[2])]) == []
    assert list(pr_opening_steps()) != [], "guard: the real discovery found nothing"


def _is_call(step) -> bool:
    run = str(step.get("run") or "")
    return any("gh pr create" in line for line in run.splitlines()
               if not line.lstrip().startswith("#"))


def test_the_exemption_is_still_earned():
    """`EXEMPT` is a dated debt with a reason, not a place to park workflows quietly."""
    for name in EXEMPT:
        text = (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "gh pr create" in text, f"{name} no longer opens a pull request — drop it from EXEMPT"
        assert "Signed-off-by" not in text, (
            f"{name} now signs its commits — re-check whether it still needs the exemption")
