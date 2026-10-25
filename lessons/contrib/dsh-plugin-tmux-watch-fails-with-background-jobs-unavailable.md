---
title: "DSH tmux_watch fails with \"background jobs unavailable: no job controller serves this agent\""
domain: "dsh"
tags:
  - "dsh"
  - "tmux"
  - "tmux-watch"
  - "background-jobs"
  - "job-controller"
  - "cordis"
  - "agent-scope"
  - "orphan-session"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "tmux_watch 报“没有 job controller”不是插件没装：启动任务时没传 owner，控制器只挂在 agent 分组里，全局层没人接单。"
trigger: "background jobs unavailable: no job controller serves this agent"
verify: "Unit probe with a fake registry: startWatchJob without owner is rejected, with owner is accepted; after a DSH restart tmux_watch returns a jobId."
source: "intake-3808"
provenance:
  issue: "#3808"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH `tmux_watch` fails with "background jobs unavailable: no job controller serves this agent"

## Problem

On a DSH host the `tmux_watch` plugin tool refused every call with:

```
background jobs unavailable: no job controller serves this agent (load @deepseek-ai/dsh-tool-jobs in its composition)
```

The message points at the composition, and the composition was fine. The reporter checked that
`@deepseek-ai/dsh-tool-jobs` was composed at profile scope **and** inside three agent-scoped groups,
then read `dsh-jobs-local`'s `resolveOwner` / `servesOwner` and the plugin's `watch.js`
`startWatchJob` spec to find where the refusal actually comes from.

Two symptoms came out of the same defect:

- every `tmux_watch` call failed with the error above, regardless of arguments;
- each failed call still created a tmux pane, so the failures leaked one orphan session per attempt.

## Root Cause

**The plugin is not missing — the job is started without an owner.** The tool's execute path calls
`jobs.start()` with no `owner`. In `dsh-jobs-local`, `servesOwner(undefined)` is true only when a
controller sits on the **global** layer. `@deepseek-ai/dsh-tool-jobs` attaches its controller inside
**agent-scoped groups**, so nothing ever sits on the global layer, and an ownerless start is always
refused. Loading the plugin again cannot fix this: the controller exists, it is just not where the
ownerless lookup looks.

**The check happens after the resource is created.** The tool creates the tmux pane first and asks the
job registry second, so the refusal arrives after the side effect. That is why the error is not only
misleading but lossy — every retry adds another pane nobody owns.

The general rule this exposes: an error that names plugin `A` can be produced by a lookup in plugin
`B`; and a refusal must be resolved before any resource is allocated, or the failure path leaks.

## Solution

### Step 1: trace `servesOwner` before changing the composition

Read `dsh-jobs-local`'s `resolveOwner` / `servesOwner`. The branch that matters is the ownerless one:
it resolves against the global layer only. Confirm that the `dsh-tool-jobs` controller is registered
inside the agent-scoped group (profile scope plus three groups in the reporter's composition), not at
the global layer. No amount of compose-config editing puts it there for this call path.

### Step 2: pass the calling session as the owner

In the plugin's tool execute path, start the job with the agent that is asking for it:

```js
jobs.start({ owner: exec.agent.id });
```

On the agent side the same value is available as `exec.agent?.id`. Do not rely on an ambient current
agent: the ownerless call is exactly the case that resolves to nothing.

### Step 3: resolve the owner before creating the pane

Reorder the tool body so that the owner is resolved — and a refusal is returned — **before** any tmux
pane is created. A rejected start must leave no session behind.

### Step 4: there is no configuration-only workaround

The intake records no config or environment flag that makes an ownerless `jobs.start()` succeed; the
fix is in the plugin code. Until it is patched, `tmux_watch` keeps failing, and each attempt can add a
pane.

## Verification

The reporter's stated check, not run in this repository:

1. **Unit probe** `startWatchJob` with a fake registry: an ownerless start is rejected, a start with
   `owner` is accepted.
2. **Live check** after a DSH restart: call `tmux_watch` again and confirm it returns a `jobId` and the
   pane is actually watched.

One more criterion follows from Step 3: trigger an ownerless start on purpose and compare `tmux ls`
before and after — after the reorder the refused call must add no session. That is the check that
catches the leak even when the happy path passes.

## Notes

- Evidence E1: the diagnosis is the reporter's, from reading the two plugins; it was not reproduced in
  this repository.
- The error text is a red herring by construction: it names `@deepseek-ai/dsh-tool-jobs` (the package
  that *has* the controller), not `dsh-jobs-local` (the lookup that fails).
- The report does not record how the already-leaked panes were cleaned up. Check `tmux ls` for sessions
  named after failed watches before retrying.
- Any other plugin that calls `jobs.start()` without an owner on an agent-scoped composition will hit
  the same refusal; the fix belongs in each execute path, not in one shared helper unless the helper
  knows which agent is asking.
