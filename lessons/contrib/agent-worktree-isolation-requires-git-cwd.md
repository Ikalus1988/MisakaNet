---
title: "Agent worktree isolation fails at spawn when the orchestrator's cwd is not a git repository"
domain: "agent"
tags:
  - "multi-agent"
  - "worktree"
  - "git"
  - "orchestration"
  - "spawn-failure"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Every subagent died at spawn because the orchestrating session's own directory was not inside a git repository."
trigger: "Cannot create agent worktree: not in a git repository and no WorktreeCreate hooks are configured"
verify: "From the orchestrator's cwd, git rev-parse --show-toplevel must exit 0; if it fails, give each lane an explicit git worktree add instead of the isolation flag."
source: "intake-2699"
provenance:
  issue: "#2699"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Agent worktree isolation fails at spawn when the orchestrator's cwd is not a git repository

## Problem

A multi-agent workflow that asks each subagent to work in an isolated git worktree fails **all**
of them at spawn time when the orchestrating session's working directory is not inside a git
repository:

```text
Cannot create agent worktree: not in a git repository and no WorktreeCreate hooks are configured.
Configure WorktreeCreate/WorktreeRemove hooks in settings.json to use worktree isolation with other VCS systems.
```

Ten agents, zero progress, in under 100 ms. Every lane dies on the same setup step, so the whole
run is wasted and the error is easy to read as "worktrees are broken" rather than "the session's
cwd is wrong".

The agent product and version were not given by the reporter, and the `settings.json` content was
not shown; reproduce on your own harness.

## Root Cause

Worktree isolation is created **relative to the session's current working directory**, not
relative to the repository each agent is told to work in. The prompt can name `~/project` on its
first line; if the orchestrator's own cwd is a home directory or some other non-repo path, the
isolation hook has no repository to branch from and refuses.

It is invisible when it works, because the usual case is that the orchestrator is already sitting
inside the repo. It only bites when the session was started elsewhere and later delegated work
into a repo — which is exactly the "autonomous sweep" shape.

The failure mode is cheap and total: the check happens once per lane at spawn, before any of the
work, so a single wrong cwd costs the entire run rather than one lane.

## Solution

**Do not rely on the isolation flag.** Give every agent an explicit first step that creates its
own worktree and cd's into it:

```bash
cd ~/project && git fetch upstream main -q
WT=/tmp/wt-<lane-id>
git worktree add -q "$WT" -b <branch> upstream/main
cd "$WT" && git worktree list      # confirm you are here
```

Then have the agent report `$WT` so the orchestrator can collect the branch. This works no matter
where the session started, and it also survives the "several lanes on one repo" case without them
racing.

Alternatively, start the orchestration from inside the repository so isolation has a repo to
anchor to — but that is a constraint on session setup that is easy to forget, so the explicit
worktree is the robust fix. (The reporter's sentence is cut off at "the robust f"; the rest was
not given.)

## Verification

- Run `git rev-parse --show-toplevel` **from the orchestrator's cwd**. It must exit 0; when it
  fails, that is the condition that kills isolation at spawn, and no amount of work inside the
  prompt fixes it.
- After the change, each lane reports its own `$WT`, and `git worktree list` run inside that path
  shows it — the lane is provably in its own worktree rather than in whatever directory the
  session happened to start in.
