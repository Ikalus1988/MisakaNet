# The branch sync, and why its pushes are special

`auto-sync-prs.yml` merges `main` into the branches of open **same-repo** PRs so contributors do not have
to keep rebasing. Fork PRs are skipped: the job cannot push to a fork.

Three things about it are not obvious, and each was found by watching it fail on a real PR
(2026-09-19).

## 1. The push must be authenticated by a user token, and the checkout must not shadow it

A push that GitHub attributes to the automatic `GITHUB_TOKEN` does not produce a *working* CI run on the
new head: the suite is created and **held** (`action_required`, zero steps executed), so the PR reads
`unstable` and nothing re-runs. A PAT fixes that — but a PAT alone is not enough, because

* `actions/checkout` writes `http.https://github.com/.extraheader` into the local git config with
  `GITHUB_TOKEN`, and
* `git -c http.extraheader=…` **appends** a second Authorization header instead of overriding it.

The server takes the checkout's, so the push stays attributed to the bot while the workflow believes it
used the PAT. `persist-credentials: false` on the checkout is what makes the PAT header the only one.

How to tell which happened — the run's `triggering_actor`:

```bash
gh api "repos/$REPO/actions/runs?head_sha=$SHA&per_page=1" --jq '.workflow_runs[0].triggering_actor.login'
# github-actions[bot] → the push was bot-authenticated (the runs will be held)
# a human login      → the PAT was used
```

## 2. The merge commit it creates must be signed off

The sync writes a commit onto someone else's branch, and this repository's DCO gate requires a
`Signed-off-by:` on every commit — so a sync without `--signoff` turns the contributor's PR red for a
commit they did not write. `git merge --signoff` fixes it, and the trailer carries the job's identity,
which is the honest attribution.

## 3. Verify the result instead of assuming it

The workflow reads its own claim back: after pushing it counts **GitHub Actions** check runs on the new
head (an app check run from Cloudflare or Codecov is not CI), counts the runs held as `action_required`,
and names the triggering actor in its warning. A sync that updates a branch without producing working CI
is worse than no sync: the PR then looks like it is waiting for something that will never arrive.

## What the sync cannot do

It cannot push to a fork, so a fork PR is never kept current by it — that is GitHub's rule, not a
missing feature. Those PRs are refreshed by their authors, or by the maintainer's `update-branch` API
call when the branch is merely behind.

## 4. It runs six-hourly, not on every push to `main` (changed 2026-10-01)

It used to be `on: push: branches: [main]`, so every main push re-headed every open PR. Measured costs on
2026-10-01:

* each sync re-runs that PR's whole cross-platform matrix (30+ checks) — at the point this was measured,
  **42 runs** were queued repo-wide;
* the push **resets GitHub's `mergeable` computation**, so a PR that was about to merge returns to
  `mergeable_state: unknown` and auto-merge stalls. The 2.40.0 release PR's head moved three times in
  about twenty minutes, and PR #2584 had to be merged through the API because a sync had re-headed it
  seconds earlier;
* what the sync buys is **optional**: `main`'s ruleset has
  `strict_required_status_checks_policy: false`, so a PR does **not** have to be up to date with `main` to
  merge. Syncing avoids conflicts accumulating, and six hours is enough for that.

The workflow now runs on `schedule: 17 */6 * * *` plus `workflow_dispatch`, and it skips any PR whose
`mergeable` is already `true`: a PR that can merge must not be pushed to at all, whatever the schedule
says. Both properties are pinned by `tests/test_auto_sync_prs.py`, which takes a workflow source as an
argument so the rule can be shown to fail.
