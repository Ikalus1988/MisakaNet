---
domain: "ci"
title: "A GITHUB_TOKEN push cannot trigger workflows, so a branch sync freezes CI"
tags: ["github-actions", "github-token", "pat", "bot-push", "workflow-trigger", "ci"]
status: "published"
evidence_level: "E0"
created: "2026-09-19"
summary_plain: "A bot that pushes to a PR branch with the built-in token updates it but starts no CI, leaving the PR stuck."
trigger: "PR shows unstable / expected waiting for status after a bot merged main into the branch; check-runs total_count is 0 on a fresh head"
verify: "After the sync push, `gh api repos/{owner}/{repo}/commits/<sha>/check-runs --jq .total_count` is > 0 within a minute, and the PR leaves `unstable`"
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

**GitHub suppresses workflow runs for events created by the automatic `GITHUB_TOKEN`.** This is
deliberate: without it, any workflow that pushes would re-trigger itself recursively. The suppression
applies to the push itself, which means:

```
git push origin "HEAD:$HEAD_REF"      # with GH_TOKEN=secrets.GITHUB_TOKEN
```

updates the branch and emits **no `pull_request: synchronize` event**. No event, no run: the PR's new
head has no checks and none are coming. Nothing in the log says so — the workflow reports success, and
the branch really was synced.

The trap is that the two halves of such a workflow want different tokens: reading PR data and
commenting work fine with `GITHUB_TOKEN`, and only the *push* silently needs a user identity. A
workflow can therefore be correct-looking for months and be quietly poisoning every PR it helps.

The repository already knew the rule — `release-please.yml` documents that a `GITHUB_TOKEN` push cannot
fire another workflow, which is why its PyPI publish is an explicit `gh workflow run` — but it was
written down where it applied, not where it bit.

## Solution

Push with a **personal access token** (or any non-`GITHUB_TOKEN` app token). Classic PAT: `repo`.
Fine-grained PAT: **Contents: Read and write** — `actions: write` is *not* needed, because nothing here
dispatches a workflow; the push itself is what triggers. A PAT push is an ordinary user push, so
`synchronize` fires and the checks run.

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
