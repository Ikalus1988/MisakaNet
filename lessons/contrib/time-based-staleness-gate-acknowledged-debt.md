---
title: "Time-based staleness gates fail on a schedule: add an acknowledged-debt marker, never bump the date"
domain: "ci"
tags:
  - "ci"
  - "gate"
  - "staleness"
  - "artifacts"
  - "verification"
  - "frontmatter"
  - "exit-code"
  - "debt"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "按天数判过期的 CI 关卡会在没有任何代码改动的一天突然变红；正确做法是加一个「已知过期」标记，而不是改日期。"
trigger: "stale artifact gate --strict exit 1 on a day with no code change / ten entries crossed the 90-day threshold / bump the dates to go green"
verify: "--strict 由 exit 1 变 exit 0，且日期字段前后逐字节相同、摘要仍打印 stale=10 (acknowledged=10)、再塞回一个未标记的过期条目仍失败。"
source: "intake-3025"
provenance:
  issue: "#3025"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Time-based staleness gates fail on a schedule: add an acknowledged-debt marker, never bump the date

## Problem

A CI gate that flags stale artifacts older than N days turned `--strict` red **on a day when
no code changed**. Ten entries crossed the 90-day threshold at the same moment, so a routine
health check suddenly blocked the whole pipeline:

```text
validator --strict   ->  exit 1
```

The report does not name the repository, the validator path, or the exact field that carries
the age — 报料者未给出，需复现确认. What it does state is the shape that matters: the red run
had an empty diff, and ten entries went stale together.

The immediate instinct — "fix" it by bumping the dates — is the trap this lesson is about.

## Root Cause

Time-based staleness gates have a property no other gate has: **they fail on a schedule,
independent of the diff**. Every entry is on a countdown, so the pipeline is guaranteed to
turn red again eventually even if nobody touches the code.

That is fine in itself — the signal is real. The failure is that the gate had only **two**
outcomes: pass, or block. There was no way to say *"this is old, I know, it has not been
re-verified"*. When the only lever that turns the gate green is the date, the cheapest way to
unblock the pipeline is to make the data look fresh:

```text
# the tempting, wrong fix
-old_date: 2026-06-01
+old_date: 2026-10-25
```

That converts a true signal into a false one. The analysis really is 90 days old; after the
bump nothing in the repository records that it was never re-verified, so the next person
reads a recent date and assumes the content was checked. The gate's whole reason for
existing — surfacing unverified age — is destroyed in the act of silencing it.

## Solution

Give the gate an explicit **acknowledged-debt marker** with precise semantics:

1. A frontmatter flag (for example `needs_reverify: true`) means "this is old, I know, it has
   not been re-verified". The marker is a *declaration*, not a suppression.
2. **The date field is never touched.** That is the entire point: the age stays visible and
   keeps growing.
3. The warning is **still printed and still counted as stale**. Declaring debt must not hide
   the condition it declares.
4. The gate has **three** outcomes, not two:

   | state | result |
   |---|---|
   | fresh | pass |
   | stale + acknowledged | warn, do not block |
   | stale + unmarked | block |

   Unmarked staleness keeps failing, so the marker cannot silently become a blanket escape.

Also build the summary line in from the start, so the debt is legible instead of buried in
hundreds of warning lines:

```text
fresh=104 stale=10 (acknowledged=10)
```

## Verification

- Ran the validator before and after: `--strict` went from **exit 1 to exit 0**.
- Confirmed the dates were untouched — a grep of the date field before and after the change is
  byte-identical. The fix did not fake freshness.
- Confirmed the warnings are still emitted and the summary still reports
  `stale=10 (acknowledged=10)`: the debt is declared, not hidden.
- Reintroduced a deliberately **unmarked** stale entry and confirmed it still fails, so the
  marker is not a blanket suppression.

## Notes

- The gate name, threshold constant and validator path are not in the report. The reproduction
  is therefore "diff an empty commit, then run `--strict` twice with and without the marker" —
  not "run this exact file".
- The same three-outcome shape applies to any gate whose failure is a function of the clock
  rather than of the diff: certificate expiry, pinned-dependency age, snapshot freshness.
- A marker nobody reads is not debt-tracked debt — if the summary line does not separate
  `stale` from `acknowledged`, "we know about it" is indistinguishable from "we hid it".
