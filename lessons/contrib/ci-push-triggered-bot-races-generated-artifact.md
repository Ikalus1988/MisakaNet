---
title: 'Push-triggered bot workflow races itself: `|| true` hides rebase conflict and leaves detached HEAD'
domain: devops
tags:
  - github-actions
  - concurrency
  - rebase
  - generated-artifacts
  - race-condition
  - git
  - ci
status: published
created: '2026-09-11'
updated: '2026-09-11'
source: leaderboard-watch-detached-head-2026-09-11
evidence_level: E1

provenance:
  source: "external"
  contributor: "Ikalus1988"
  merged_at: "2026-09-11"
  evidence: "post-publication"
---

# Push-triggered bot workflow races itself: `|| true` hides rebase conflict and leaves detached HEAD

## Problem

A workflow that **runs on every push to main, generates a file, and commits it** fails
intermittently — but only when two pushes land close together. The failing step's log ends with
something like:

```text
CONFLICT (content): Merge conflict in data/leaderboard_meta.json
error: could not apply 0dae5f4c... chore: update leaderboard snapshot [skip ci]
hint: Resolve all conflicts manually, mark them as resolved with ...
fatal: You are not currently on a branch.
To push the history leading to the current (detached HEAD)
state now, use

    git push origin HEAD:<name-of-remote-branch>

##[error]Process completed with exit code 128.
```

The message is misleading: the step *does* start on a branch, and the previous run of the same
workflow succeeded. Nothing in the repository was edited by a human.

## Root Cause

Three ingredients, all of them individually reasonable:

1. **Trigger shape.** `on: push: branches: [main]` starts one workflow run per push. Two pushes
   a minute apart start **two concurrent runs**.
2. **Both runs write the same generated artifact.** Each run computes the snapshot from its own
   checkout and then commits it (`data/leaderboard_meta.json` here — any generated JSON/CSV behaves
   the same). The first run pushes its commit; main has now moved.
3. **The rebase is allowed to fail silently.** The step contained:

   ```bash
   git pull --rebase origin main || true
   git push
   ```

   The second run's rebase now replays its snapshot commit on top of the *other* run's snapshot
   commit. Both changed the same fields → content conflict. `|| true` swallows the non-zero exit,
   and a conflicted rebase is **not** a no-op: git leaves the worktree in a rebase-in-progress state
   with a **detached HEAD**. The next command, `git push`, therefore dies with
   `fatal: You are not currently on a branch` (exit 128) — an error that points at the wrong thing.

So the race is the trigger, but `|| true` is what converts a *resolvable* conflict into a *confusing*
hard failure. A conflicted rebase must never be ignored: unlike a failed `git pull --ff-only`, it
mutates repository state that later commands depend on.

## Solution

Three changes, in order of importance:

**1. Stop swallowing the rebase failure.** Fail loudly and leave a clean tree:

```bash
if ! git pull --rebase -X theirs origin main; then
  echo "::error::rebase onto origin/main failed; leaving a clean tree"
  git rebase --abort || true
  exit 1
fi
git push
```

**2. Serialize the runs** so the race mostly cannot happen:

```yaml
concurrency:
  group: leaderboard-watch
  cancel-in-progress: false
```

`cancel-in-progress: false` matters: cancelling the queued run would drop a snapshot; letting it run
means it starts from the newest main.

**3. Resolve artifact conflicts in favour of the fresh computation** with `-X theirs`. In a **rebase**,
`theirs` is the commit being replayed — i.e. *your* freshly generated file — while `ours` is upstream.
This is the opposite of the intuition people carry from merges, and it is exactly what you want for a
generated artifact: the newest snapshot wins, upstream's unrelated changes are kept.

Cheaper structural fixes worth considering instead, when applicable: commit the artifact only from a
`scheduled` (cron) trigger where runs are naturally spaced, don't commit generated output at all, or
have the workflow open a PR instead of pushing to main.

## Verification

A conflicted rebase is easy to reproduce in a scratch repo without touching CI — create a bare remote,
push a "base", then simulate the two racing runs:

```bash
git init -q --bare remote.git && git clone -q remote.git work && cd work
git config user.email t@t; git config user.name t
mkdir -p data && printf '{"rank":1,"ts":"T0"}\n' > data/leaderboard_meta.json
git add -A && git commit -qm base && git push -q -u origin HEAD:main

# the other concurrent run lands on main first
printf '{"rank":9,"ts":"OTHER"}\n' > data/leaderboard_meta.json
git commit -qam "other run snapshot" && git push -q origin HEAD:main
git reset -q --hard HEAD~1

# our run computed its own snapshot, then commits and tries to push
printf '{"rank":5,"ts":"OURS"}\n' > data/leaderboard_meta.json
git commit -qam "update snapshot [skip ci]"

git pull --rebase origin main            # -> CONFLICT, rebase in progress
test -d .git/rebase-merge && echo "detached mid-rebase: yes"
git rebase --abort

git pull --rebase -X theirs origin main  # -> Successfully rebased
cat data/leaderboard_meta.json           # -> {"rank":5,"ts":"OURS"}
git symbolic-ref -q --short HEAD         # -> main  (still on a branch, push will work)
```

Observed on both branches of the experiment: the naive rebase stops mid-conflict with a detached
HEAD, while `-X theirs` completes and keeps the freshly computed content. The production failure that
motivated this was a real GitHub Actions run whose log contains all three signatures —
`CONFLICT`, `could not apply`, and `fatal: You are not currently on a branch` — inside the *same*
step.

## Detection Heuristics

- `fatal: You are not currently on a branch` almost always means **an earlier rebase in the same
  step failed and was ignored** — look *up* the log for `CONFLICT` before touching the push command.
- A bot-commit step that is green on isolated pushes and red on bursts of activity is a concurrency
  bug, not a flaky network.
- Any `git pull --rebase ... || true` in CI is a latent instance of this pattern; grep for it.
