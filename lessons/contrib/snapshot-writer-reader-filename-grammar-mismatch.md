---
domain: "development"
title: "A snapshot writer and reader with different filename grammars silently keep the history dead"
tags:
  - "snapshot"
  - "persistence"
  - "filename-grammar"
  - "round-trip-test"
  - "silent-failure"
  - "stale-data"
  - "default-off"
  - "write-rate"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3369"
summary_plain: "The history feature wrote snapshot filenames its reader never matched, so every run diffed against a months-old file."
trigger: "transition diff always compares against a stale snapshot; newly written snapshots never selected"
verify: "After one run the reader picks the file that run just wrote, not an older one; the next run reports skipped_write='state unchanged since previous snapshot'."
provenance:
  issue: "#3369"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A snapshot writer and reader with different filename grammars silently keep the history dead

## Problem

A status-snapshot engine persisted one file per run and reported the difference between "current"
and "previous" — the product feature was a *PR status transition history*. It wrote files; the
reader never picked them up.

- The writer named snapshots `YYYY-MM-DD-HHMM.json`.
- The reader's regex accepted only `YYYY-MM-DD.json`.

The reader's pattern had been tightened to exclude test fixtures such as `YYYY-MM-DD-graphql.json`,
and the new writer shape was caught in the same filter. So every run compared "current vs previous"
against a **months-stale** file, forever. The feature looked alive in code review and recorded
nothing usable.

The reported symptom, verbatim:

```
transition diff always compares against a stale snapshot; newly written snapshots never selected
```

A second, independent reason the history was empty: the recording switch **defaulted to off**, and
three call sites hard-coded it off while two used the flag. Even with a fixed reader, a run started
from one of those three call sites would have found an empty directory.

## Root Cause

**Two grammars, one artifact.** The name was written by one piece of code and recognised by another,
and neither piece knew the other's production rules.

The tests made this invisible: there were tests for the writer's name shape *and* tests for the
reader's strictness, but **no save→find round-trip test**. Both sides could be individually correct
and still disagree — which is exactly what happened. A per-side unit test cannot fail on a contract
between the two sides, because it never crosses the boundary.

The tightening step added a second trap. A matcher was narrowed to reject fixture names
(`YYYY-MM-DD-graphql.json`) and was checked against *the names it should reject*, not against *every
name a producer emits*. Any filter that exists to exclude noise is also a filter that can exclude
signal, so a matcher change needs an inventory of producers, not just an inventory of rejects.

The third factor is a design error rather than a matching error: a feature whose whole value is
*memory* shipped opt-in. History has holes wherever a human ran the tool by hand, and no amount of
reader correctness fills them.

## Solution

### Step 1 — one shared name grammar

Keep the write-path and read-path filename grammar in a single constant/function pair. Accept both
the legacy daily name and the timestamped name; keep the fixture-name rejections explicit rather
than implied by a single anchored pattern.

### Step 2 — order by parsed time, not by string

Order snapshots chronologically by **parsed date + minute**, not lexicographically. Lexicographic
order across mixed shapes is the same class of mistake: `2026-10-01.json` and
`2026-10-01-1345.json` are not a total order that means "older first".

### Step 3 — add the round-trip regression lock

The regression test is *write → read-back finds it*:

```
save (one snapshot)  →  find (previous snapshot)  →  assert found == the file just written
```

That single assertion fails on the old code (it picked the two-month-old file) and is the only test
that can catch this class of bug. Per-side tests do not substitute for it.

### Step 4 — record by default, bound the rate in the writer

- Recording is **default-on**, with an explicit `--no-opt-out` flag for the rare caller that must not
  record — the reporter's wording.
- The write policy is: record a state **change immediately**, and write **at most one heartbeat per
  interval** when the state is unchanged. This is the fix for directory flooding: bound the write
  rate inside the writer instead of relying on callers to poll politely.

The reporter reproduced the mismatch before fixing it with a one-liner asserting
`reader-pick != just-written file`; on the old code the reader picked the two-month-old file. The
exact one-liner and the exact flag spellings were **not quoted in the report (报料者未给出，需复现确认)**.

## Verification

- **Round-trip test passes**: write one snapshot, ask the reader for the previous one, get the file
  that was just written. Fails before the fix (it returned the two-month-old file).
- **Live run against real API data**: the transition diff is computed against the correct previous
  snapshot, and a new snapshot file appears on disk (`ls` of the snapshot directory shows it).
- **Second run**: reports `skipped_write='state unchanged since previous snapshot'` — the heartbeat
  bound works and no duplicate is written.
- **Empty-directory run**: reports "first record / baseline established", and invents no durations.
- **Suite**: 745 tests pass; the only failures are 4 pre-existing data-file tests that fail
  identically on a clean checkout.

## Notes

- The product and its snapshot directory are not named in the report; paths and the actual regex were
  not quoted (报料者未给出，需复现确认). The mechanism, however, is language- and product-independent:
  every "diff today against yesterday" feature has exactly this failure mode.
- Two lessons in one, and both are needed: (a) a shared write/read grammar with a round-trip test,
  (b) a history feature that is on by default and rate-bounded at the writer.
- Related shape, different symptom: an artifact that is written but never read is not "working code
  with a display bug" — it is a persistence layer that is silently dead, and no test that stays on
  one side of the boundary can see it.
- Evidence level is E1: reporter-described, with measured counts, but not reproduced in this
  repository.
