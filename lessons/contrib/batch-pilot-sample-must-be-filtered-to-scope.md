---
title: "A batch job's pilot sample must be filtered to scope first, or the pilot lands outside it and re-runs"
domain: "automation"
tags:
  - "automation"
  - "batch-job"
  - "pilot"
  - "scope-filter"
  - "sampling"
  - "rework"
  - "planning"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "批量任务要先定范围再挑试点；按「谁有数据就挑谁」挑，试点会全落在被排除的分组里，白跑一遍。"
trigger: "试点 5 台全在要排除的分组里 白跑 重做 批量任务 先定范围再挑样本"
verify: "试点名单能列出排除了谁及原因，且样本集合 ⊆ 目标范围、范围内每个分组都有代表。"
source: "intake-3567"
provenance:
  issue: "#3567"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A batch job's pilot sample must be filtered to scope first, or the pilot lands outside it and re-runs

## Problem

A batch generation task started with a "pilot on 5 machines". The pilot completed cleanly — 5/5 — and
only then did the operator discover that **all five were inside the group the user had explicitly
excluded**. Five runs were wasted, and the correct 58 had to be run afterwards.

The reporter's own error line:

```
试点 5 台全部落在用户明确排除的分组里，白跑后重做
```

## Root Cause

The pilot's sample was ordered by **data availability** only — "pick whoever has data" — with no
business-scope filter applied first, and the "which ones?" question was only asked at the batch phase,
when it was too late to un-choose the sample.

That is two prerequisites of a batch job being treated as one:

- **Scope** — which objects the run is about. A business constraint. Must be fixed first.
- **Availability** — which of them have data. A technical constraint. Applied *inside* the scope.

Reverse the order and the pilot objects fall outside the scope, so the pilot's conclusions do not apply
to what will actually be run, and the run must be redone. The quieter damage is in the estimates: a
result like "5/5 succeeded, X minutes" gets read as a projection for the scope even though it was
measured on objects that are not in the scope at all.

## Solution

The standard order for a batch job:

```text
① fix scope (business filter: exclude X / only Y)
   ↓
② stratify availability inside the scope (has data / none / partial)
   ↓
③ pick the pilot from "inside scope ∩ has data"
   ↓
④ run the pilot → ⑤ full run
```

**Hard criterion:** before the pilot starts, you must be able to list **who was excluded and why**. If
you cannot answer "which objects are not part of this run", scope was never fixed and the pilot must
not start.

Two companions the reporter added:

1. **The pilot must cover the representative groups inside the scope.** If the scope has N groups, take
   samples from each of the N; a sample drawn from a single sub-group cannot warn you about the others.
2. **Put the filter in the tool** — `--exclude-prefix`, `--area`, or equivalent — **not in a hand-picked
   list**. The reporter's actual fix was exactly this: filter by area prefix first, then sample, and
   move `--exclude-prefix` into the tool. A hand-picked list is re-derived by hand every time and
   repeats the mistake.

## Verification

After the pilot finishes, check two things before the full run:

- **sample set ⊆ target scope** — no pilot object may be outside the scope, and
- **every group inside the scope has a representative** in the pilot.

Pass = both hold and you can name the excluded group(s). Fail = any sample falls outside the scope; in
that case **stop the batch and re-run the pilot**. Do not continue with "the tool works anyway, just
run the rest": once the sample is out of scope, both the duration estimate and the error-rate estimate
are already invalid, so the full run would be executed against numbers that describe different objects.

## Notes

The reporter gave the rework cost (5 pilot runs wasted, 58 correct ones re-run) but not the batch's
runtime per object, so the wall-clock loss is **报料者未给出，需复现确认**.

The same ordering applies to any "sample to estimate, then run the rest" design, including
machine/device fleets and repository-wide code transformations: an estimate measured outside the
selection you will act on is not an estimate of that selection.
