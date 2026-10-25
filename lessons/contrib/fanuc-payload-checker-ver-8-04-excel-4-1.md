---
title: "FANUC Payload Checker 8.04 reimplementation: four payload data-source traps that flip OK/WARN verdicts"
domain: "fanuc"
tags:
  - "fanuc"
  - "payload-checker"
  - "payload"
  - "plst-grp1"
  - "plid"
  - "armload2"
  - "j3j6-envelope"
  - "robot-backup"
  - "excel-macro"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "复刻 FANUC Payload Checker 时四个取数口径错了会让利用率全错：当前负载看 $GROUP[1].$PAYLOAD 命中的 PLST 组，ARMLOAD2 要当 0，分母走 J3/J6 包络插值。"
trigger: "Payload as % of Max Allowed denominator mismatch; ARMLOAD2=550; $GROUP[1].$PAYLOAD PLST group selection"
verify: "Against the Excel formula path (AutomationSecurity=3, macros off) on 182 backups, torque/inertia %, payload utilisation, OK/WARN/OVER and Warranty match at 0.15% tolerance."
source: "intake-3677"
provenance:
  issue: "#3677"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# FANUC Payload Checker 8.04 reimplementation: four payload data-source traps that flip OK/WARN verdicts

## Problem

Rebuilding the wrist-payload check of FANUC's Payload Checker (ver 8.04) Excel macro, and running it in
bulk over robot backups, four data-source conventions (口径 — i.e. which value means what) produced wrong
numbers. Torque % and inertia % could look right while payload utilisation and the OK/WARN tier were
wrong; some robots came out with a zero limit or a collapsed utilisation.

The reported mismatch signature:

```
Payload as % of Max Allowed denominator mismatch; ARMLOAD2=550 breaks envelope limit
```

The four traps, as the reporter hit them:

1. `ERRCURR.LS` prints `PAYLOAD :` — that is the **robot model's rated payload** (the nameplate value),
   not the tool or gun payload. Cross-checking the tool payload against it yields wrong conclusions.
2. The current tool payload is not read from `$PLID_GRP1` (empty on most robots). It is the
   `$PLST_GRP1[n]` group hit by `$GROUP[1].$PAYLOAD` — the set the program is actually using. Picking the
   wrong group returns a spare tooling set, or an Uninitialized rated placeholder.
3. `$PLID_GRP[1].$ARMLOAD2` reads 550 on every model. That is an **uninitialized default**, not the J3
   arm shell load. Treating it as shell load in the J3/J6 combined envelope makes the limit 0, and
   payload utilisation collapses.
4. The denominator of "Payload as % of Max Allowed" is not the nameplate rating. It is the **J3/J6
   combined envelope interpolation**: the tool's `J3J6Table` gives three envelope blocks, and the cap is
   the MIN after piecewise-linear interpolation. An R-2000iC/270F at J3 load = 0 caps at 285 kg, not
   270 kg — a 5-10% difference, enough to flip an OK/WARN tier.

## Root Cause

All four are **data-source** errors, not arithmetic errors. That is why a perfectly correct formula can
still produce a wrong verdict: the numbers fed into it describe a different quantity than the one the
check means.

**1. The nameplate is not the tool load.** `ERRCURR.LS` is a text dump; its `PAYLOAD :` line is the
model's rated payload. The correct use the reporter settled on is a cross-check against the model
library's rated value — nothing else. Feeding it into the tool-load path compares a machine limit with a
tool mass.

**2. The active payload set is chosen by `$GROUP[1].$PAYLOAD`.** On most robots `$PLID_GRP1` is empty, so
reading it yields nothing useful. The value the program uses selects one `$PLST_GRP1[n]` group, and that
group is the one carrying the mass, COG and inertia currently in use. Selecting by array index instead
of by that group picks whatever else is stored — a spare tooling set, or an uninitialized rated
placeholder.

**3. 550 is a sentinel, not a measurement.** `$PLID_GRP[1].$ARMLOAD2` is 550 on all models; the fact that
it is identical across machine types is the tell. It is the uninitialized default. Passed into the J3/J6
combined envelope as if it were shell load, it makes the computed limit 0, so payload utilisation
collapses.

**4. The cap is interpolated from the tool's `J3J6Table`.** Three envelope blocks, points 0 / `$CC` /
`$DD` / `$EE` against `$AA` / `$AA` / `IF(type=3,0,$BB)` / 0, piecewise-linear between points, then the
MIN across the blocks. Using the nameplate instead is off by 5-10% in the R-2000iC/270F example (285 kg
vs 270 kg at J3 load = 0), which is enough to move a robot between OK and WARN.

## Solution

The report's fix has four parts, one per trap.

### Step 1: select the payload group in three stages

Pick the active payload set in this order:

1. `PLID` — the payload ID for this robot (the report calls this level 1);
2. the `$PLST_GRP1[n]` group matched by `$GROUP[1].$PAYLOAD` (the group the program uses);
3. the first candidate group with a non-zero CG.

That ordering is what keeps the selection on the program's own set instead of an index that happens to
be populated. The report names the three levels but not the exact query for each, so level 1 is the
payload ID as recorded in the backup rather than a specific `$`-variable path.

### Step 2: treat `$ARMLOAD2` as 0

Do not pass the 550 default through to the envelope. The report's fix pins `$ARMLOAD2` to 0 in the
calculation, so the J3/J6 limit is not driven to zero by a value that was never written by the robot.

### Step 3: compute the denominator from the J3/J6 envelope

Implement the `J3J6Table` interpolation literally:

- points on the J3-load axis: 0, `$CC`, `$DD`, `$EE`;
- values at those points: `$AA`, `$AA`, `IF(type=3,0,$BB)`, 0;
- piecewise-linear between adjacent points;
- take the MIN across the three blocks as the cap;
- divide the tool payload by that cap.

Keep a known-machine fixture: R-2000iC/270F at J3 load = 0 must cap at 285 kg, not the 270 kg
nameplate.

### Step 4: keep `ERRCURR.LS` `PAYLOAD :` for the nameplate cross-check only

Read it to compare against the model library's rated payload. Never use it as the tool payload, and
never as the utilisation denominator.

## Verification

The reporter's cross-check, run over 182 robot backups:

1. Open the workbook through Excel COM with `AutomationSecurity=3` (macros disabled without prompting),
   so the formula path evaluates and the macro does not run.
2. Compare the Python reimplementation against those formula results.

Fields compared: torque %, inertia %, payload utilisation, the four-tier verdict OK / WARN / OVER
(`OVER(CHK)`), and Warranty. Tolerance 0.15%; the reported result is 0 differences across all 182
backups.

A single-machine smoke test before the batch: load the R-2000iC/270F fixture and confirm the cap is
285 kg at J3 load 0, and that the four-tier verdict matches the workbook for that row.

## Notes

- Evidence E1: the reporter ran the formula-vs-engine comparison on 182 backups; it was not reproduced in
  this repository.
- `AutomationSecurity=3` is the setting that disables macros without prompting. The comparison is only
  meaningful while the workbook's formulas evaluate and the macro does not run.
- The extraction side — reading `ERRCURR.LS` and `$PLST_GRP1` values out of `.VR`/`.SV` backups — is
  covered by `lessons/contrib/fanuc-backup-payload-extraction.md`; this lesson assumes those values are
  already extracted.
- The report does not give the exact `J3J6Table` layout for every model family. Validate the interpolation
  against the workbook for the models you actually run before trusting it in bulk.
- A genuinely non-zero arm shell load, if a backup carries one, needs separate validation: the 550 default
  cannot by itself distinguish "uninitialized" from "real".
