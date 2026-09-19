---
domain: "ci"
title: "A GITHUB_TOKEN push cannot trigger workflows, so a branch sync freezes CI"
tags: ["github-actions", "github-token", "pat", "bot-push", "workflow-trigger", "ci"]
status: "published"
evidence_level: "E0"
created: "2026-09-19"
summary_plain: "A bot push to a PR branch can leave the PR with a workflow suite that is held instead of running, so CI never runs."
trigger: "PR unstable / waiting for status after a bot pushed to the branch; no check runs on the fresh head, or runs sitting in action_required"
verify: "On the pushed head, no run sits in action_required and at least one check run comes from github-actions — any check run is not enough (an app check can be the only one)"
provenance:
  source: "MisakaNet repository, 2026-09-19: auto-sync-prs.yml froze PR #1870"
---

# A GITHUB_TOKEN push cannot trigger workflows, so a branch sync freezes CI

## Problem

A repository automation merges `main` into the branches of open same-repo PRs, so contributors do not
have to keep rebasing. It worked as designed and still broke every PR it touched:

* the merge commit appears on the branch (`github-actions[bot]`, subject
  `Merge remote-tracking branch 'origin/main' into <branch>`);
* the PR's head changes — and its check runs are now **zero**;
* GitHub reports the PR as `unstable` / *"Expected — Waiting for status to be reported"*;
* nothing re-runs, ever, because nothing new happens to that commit; and
* the only way out is a human pushing an empty commit to shake CI loose.

Observed on PR #1870: the head carried 48 check runs before the sync, and 1 after it. The contributor
sees a PR that cannot merge and a UI that says it is waiting for checks that will never appear.

## Root Cause

There are **two** distinct ways this goes wrong, and the first version of this lesson only described
one of them — with the wrong mechanism. Both were measured on the same job on 2026-09-19, so read them
in order.

### 1. The push is attributed to the bot, and the suite is created *held*

```
git push origin "HEAD:$HEAD_REF"      # authenticated by GITHUB_TOKEN
```

The branch is updated, and the `pull_request` runs for the new head are created in the
**`action_required`** state and execute **not one step**:

```
check suites on the synced head: 18 total, 14 of them github-actions / action_required / runs=0
```

No failed step, no log, nothing to read — and the PR sits at `unstable` / *"Expected — Waiting for
status to be reported"* forever, because nothing new happens to that commit.

Which identity pushed is visible on the run, and this is the field to look at:

```bash
gh api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=1" --jq '.workflow_runs[0].triggering_actor.login'
# github-actions[bot] → bot-authenticated, the runs will be held
# a human login      → the push came from a user token
```

An earlier version of this lesson said a `GITHUB_TOKEN` push produces **no run at all**. That came from
a `head_sha` query that returned nothing; the same commit's check *suites* show the held runs. The
distinction matters because the fix is not "get any token": it is "get a token whose identity is
trusted to run workflows".

### 2. A PAT is not enough while the checkout keeps its own credential

`actions/checkout` writes `http.https://github.com/.extraheader` into the local git config with
`GITHUB_TOKEN`. A later

```bash
git -c http.extraheader="$AUTH_HEADER" push origin "HEAD:$HEAD_REF"
```

**appends** a second Authorization header rather than replacing the first, and the server takes the
checkout's. So the workflow logs "pushing with the PAT" while the run's `triggering_actor` is still
`github-actions[bot]` — which is exactly how this was caught, after a PAT had already been installed and
the symptom did not change.

The fix is one line on the checkout:

```yaml
- uses: actions/checkout@<sha>
  with:
    fetch-depth: 0
    persist-credentials: false      # the only Authorization header is then the one we set
```

### 3. And the merge commit it writes needs a sign-off

A job that merges `main` into someone else's branch writes a commit **onto their PR**, and a DCO gate
requires a `Signed-off-by:` trailer on every commit — so without `--signoff` the contributor gets a red
check for a commit they did not write:

```bash
git merge --signoff origin/main --no-edit
```

Measured on #1879 (no signoff → `DCO Check` failure on the synced head) and on #1882 (signoff in place →
`DCO Check` success, with the trailer naming the job: `misakanet-sync-bot <bot@misakanet.dev>`).

## Solution

Push with a **personal access token** (or any non-`GITHUB_TOKEN` app token) — classic: `repo`;
fine-grained: **Contents: Read and write**. `actions: write` is *not* needed: nothing here dispatches a
workflow, the push itself is what triggers.

Then make sure the PAT is the credential that is actually used (`persist-credentials: false`, above),
sign the merge commit (`--signoff`, above), and **read the result back**: the runs' `triggering_actor`
plus the count of `github-actions` check runs is the whole diagnosis, and it is one API call.

Two details worth keeping, both learned the hard way:

1. **Never write the fallback as `secrets.A_PAT || secrets.GITHUB_TOKEN`.** `||` here falls back only
   when the first value is *empty*, never when it is merely insufficient — so an expired PAT silently
   becomes the token that cannot trigger CI. **Skip and warn instead of syncing:**

   ```bash
   if [ -z "${SYNC_TOKEN:-}" ]; then
     echo "::warning::PAT is empty — skipping the sync. Syncing with GITHUB_TOKEN would update these
   branches without triggering any CI, leaving every synced PR 'unstable' with nothing to re-run."
     exit 0
   fi
   ```

2. **Keep the token out of a remote URL.** A remote URL that embeds credentials (the
   `https://<user>:<token>` userinfo form) leaks into error output and is what secret scanners flag; a
   git config header does not:

   ```bash
   AUTH_HEADER="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$SYNC_TOKEN" | base64 -w0)"
   git -c http.extraheader="$AUTH_HEADER" push origin "HEAD:$HEAD_REF"
   ```

### And the second half: a PAT push can create runs that are *held*

Fixing the token is necessary and not sufficient. The first sync performed with a PAT in place produced
**fourteen `pull_request` runs on the new head, every one of them `action_required`** — created, held
for approval, never executed. A different token moved the failure from "no run exists" to "the run
exists and is waiting for a human":

```
2026-09-19T13:54:30Z  DCO Check           8843f61e4  pull_request  completed/action_required
2026-09-19T13:54:30Z  Cross-Platform Tests 8843f61e4  pull_request  completed/action_required
… twelve more, all with latest_check_runs_count = 0
```

Holding happens when GitHub does not trust the push's *actor* to run workflows on that ref — the
repository's fork/outside-collaborator approval policy, applied to whoever the token belongs to. In this
repository the accumulated backlog of such runs was **1,804** on 2026-09-19, so it is the normal state
of bot-pushed branches, not an edge case.

What to do about it:

* push with a token owned by an account whose pushes are trusted on the repository (its owner or a
  member) — the same PAT that can write to the API is not automatically one whose pushes trigger CI;
* when a run is already held, a maintainer can release it:
  `gh api repos/{owner}/{repo}/actions/runs/<run_id>/approve -X POST` (or *Approve and run* in the UI);
* and prefer a push you make yourself when the automation is the thing being tested — a human push has
  no approval step to lose.

### Detection must count the right thing

The read-back above was first written as "are there any check runs on the new head?", and it reported
success on a head whose fourteen Actions runs were all held — because a **non-Actions** check run was
present (Cloudflare Workers Builds publishes a check run for the site). One green check from an app that
does not use workflow events is not CI. Count what the claim is about:

```bash
# how many check runs on this head came from GitHub Actions?
gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100" \
  --jq '[.check_runs[] | select(.app.slug == "github-actions")] | length'

# and how many *runs* on this head are held rather than running?
gh api "repos/$REPO/actions/runs?head_sha=$SHA&status=action_required" --jq '.total_count'
```

## Verification

"The push succeeded" is not the claim — "the PR's checks run again" is, so read it back per synced PR:

```bash
for attempt in $(seq 1 6); do
  COUNT=$(gh api "repos/$REPO/commits/$SHA/check-runs" --jq '.total_count')
  [ "$COUNT" -gt 0 ] && { echo "PR #$NUM: $COUNT check run(s) — CI is running"; break; }
  echo "::warning::PR #$NUM has no check runs on the synced head — the push did not trigger CI"
  sleep 10
done
```

Pass: the job log shows `Merged main into #N` followed by `PR #N: <n> check run(s) — CI is running`,
and the PR leaves `unstable`. Fail: the warning appears — and with it, the difference between a token
that cannot trigger workflows and a sync that simply had nothing to do.

To inspect it by hand on any commit:

```bash
gh api repos/{owner}/{repo}/commits/<sha>/check-runs --jq '.total_count'   # 0 = no CI was ever started
```
