---
domain: "ci"
title: "A fork PR's workflow run is created as action_required: the suite exists and never executes"
tags: ["github-actions", "fork-pr", "action-required", "pull-request-target", "approval", "ci"]
status: "published"
evidence_level: "E0"
created: "2026-09-19"
summary_plain: "A fork PR's workflow run can be held as action_required and never execute, so the automation is silently inert."
trigger: "workflow run conclusion action_required on a pull_request from a fork; check suite exists but latest_check_runs_count is 0"
verify: "GET /repos/{owner}/{repo}/commits/<head-sha>/check-suites shows success/running instead of action_required, and the job log contains real step output"
provenance:
  source: "MisakaNet repository, 2026-09-19: Auto-Merge Docs PRs on PR #1801 (fork)"
---

# A fork PR's workflow run is created as action_required: the suite exists and never executes

## Problem

A maintainer-side workflow is supposed to react to a label on a contributor's PR. The contributor is
from a fork. The label is applied, the event exists in the PR timeline, and **nothing happens**:

* `gh run list` shows the workflow, with the conclusion **`action_required`**;
* the PR's checks page shows nothing useful;
* the job log is empty, because **not one step ever ran** — so there is no error to read, and no
  "skipped" line either. The automation looks installed and is inert.

The raw evidence, for a fork PR (`GET /repos/{o}/{r}/commits/{sha}/check-suites`):

```
2026-09-17T23:06:43Z  DCO Check                 completed/action_required   runs=0
2026-09-17T23:06:43Z  PR Genius Check           completed/action_required   runs=0
2026-09-17T23:06:44Z  Auto-Merge Docs PRs       completed/action_required   runs=0
2026-09-17T23:06:44Z  Cross-Platform Tests      completed/action_required   runs=0
… eight suites created, none of them executed a step
```

A second, quieter version of the same symptom: the PR was opened against a **stale feature branch**
(`agent/issue-1196-…`) rather than `main`. `pull_request` events evaluate the workflow file from the
**base** branch, so the automation it triggered was whatever that old branch contained — a version
predating the feature the maintainer was trying to use. Retargeting the PR to `main` is what made the
run mean anything.

## Root Cause

For a `pull_request` event from a fork, GitHub creates the run **held for approval** when the
contributor is a first-time contributor (repository setting: *Require approval for first-time
contributors*, the default). The run sits in `action_required` until a maintainer clicks
*Approve and run*. Until then:

* the workflow file is resolved (usually from the base branch's merge commit), which is why a stale
  base runs an old definition;
* the token is read-only, so anything that writes — a comment, a label, a merge — would fail anyway
  (see the related lesson `ci-fork-pr-no-comment-token`);
* and, crucially, the *absence* is indistinguishable from "the condition did not match". Both look
  like a green run that decided to do nothing.

So a channel whose entire purpose is to serve external contributors can be dead for exactly those
contributors, with no signal anywhere in the repository.

## Solution

Pick by what the workflow does with the PR:

1. **Automation that only reads the PR through the API and writes to the PR** (labels, comments,
   merges): trigger it with **`pull_request_target`**. It evaluates the *base* branch's workflow (so
   the maintainer's own version always applies), runs with a write token, and does **not** wait for
   per-PR approval.

   ```yaml
   on:
     pull_request_target:
       types: [opened, synchronize, ready_for_review, labeled]
   ```

   **The safety condition is not optional, so state it in the file:** this trigger is safe *because*
   the workflow never checks out the PR, never executes anything from the diff, and only calls the
   REST API with values GitHub supplies. The related lesson `ci-fork-pr-no-comment-token` says the same
   thing from the other direction — *"Never move the whole audit job to `pull_request_target` to fix a
   comment"* — because a workflow that runs the contributor's code with a write token is the textbook
   exploit. Pin that property with a test (`assert "actions/checkout" not in <workflow code>`) so a
   later edit cannot reintroduce it quietly.

2. **Workflows that must execute the PR's code**: stay on `pull_request`, and expect the approval gate.
   A maintainer approves the held runs:

   ```bash
   gh api repos/{owner}/{repo}/actions/runs/<run_id>/approve -X POST
   ```

   (Or *Approve and run* in the Actions UI.) Automating that away is the vulnerability in (1).

3. **Check the base branch first.** A PR targeting anything other than the default branch is running
   that branch's workflow definitions; retarget it before debugging the automation:

   ```bash
   gh api repos/{owner}/{repo}/pulls/<n> --jq '.base.ref'    # not "main"? that is the bug
   gh api repos/{owner}/{repo}/pulls/<n> -X PATCH -f base=main
   ```

## Verification

The run must show **executed steps**, not just a status:

```bash
gh api repos/{owner}/{repo}/commits/<head-sha>/check-suites \
  --jq '.check_suites[] | "\(.created_at) \(.app.slug) \(.conclusion) runs=\(.latest_check_runs_count)"'
```

Pass: no `action_required` among them, and the job log carries the workflow's own output — in the case
that produced this lesson, the gate printed `Docs-only: false (3 files)`, which is proof it ran *and*
that its decision was a real one. Fail: a suite whose `latest_check_runs_count` is 0, or a conclusion of
`action_required`, means the automation never got to decide anything.
