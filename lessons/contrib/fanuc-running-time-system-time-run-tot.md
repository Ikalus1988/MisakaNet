---
title: "FANUC running time is $SYSTEM_TIME[n].RUN_TOT inside SYSVARS.SV, in minutes — not in .DG files"
domain: "fanuc"
tags:
  - "fanuc"
  - "sysvars"
  - "kconvars"
  - "system-time"
  - "running-time"
  - "utilization"
  - "offline-extraction"
  - "binary-backup"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "FANUC 的运行时长是 SYSVARS.SV 里的 $SYSTEM_TIME[n].RUN_TOT，转成文本才能读，单位是分钟不是秒。"
trigger: "FANUC running time $SYSTEM_TIME RUN_TOT SYSVARS.SV kconvars"
verify: "转换后的 sysvars_out.txt 中含 $SYSTEM_TIME[n].RUN_TOT 且数值等于控制器 sys timer 界面显示"
source: "intake-3675"
provenance:
  issue: "#3675"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# FANUC running time is $SYSTEM_TIME[n].RUN_TOT inside SYSVARS.SV, in minutes — not in .DG files

## Problem

Needed the running time (运行时长) of 300 FANUC robots for offline utilization / health analysis,
without walking up to each teach pendant. The question was where the number actually lives: in the
full backup, or only on the UI's `sys timer` screen?

Two wrong turns cost the first attempts:

- Looking for the value in `.DG` diagnostics (`SUMMARY.DG`, `irdg_report.dg`) because a workflow
  document said those contain PWR/SRV/RUN/WAIT. Measured, that file has 12 sections — Version,
  CONFIG, MOTOR, SERVO, Memory, ProgramStatus, IO, Safety, Position, Ethernet, Port, Macro — and
  **no running-time section at all**.
- Running a string search over the raw `SYSVARS.SV`: `grep "SYSTEM_TIME"` matched **0 times**, which
  reads as "the parameter is not in the backup". It is in there; the file is pure binary.

## Root Cause

The counter is the system variable **`$SYSTEM_TIME[n].RUN_TOT`** — the same array carries
`PWR_TOT` / `SRV_TOT` / `WIT_TOT` / `SHM_TOT`, each with a `_LAP` single-run value, declared as
`ARRAY[2] OF SYSTEM_TIMER` (one per motion group). It is declared `Storage: SHADOW`, so it lives in
controller shadow memory and only appears in the backup through `SYSVARS.SV`.

The UI is a display layer over the same variable, and the names differ by truncation. The controller
log shows it:

```
[vmfndvar] [*SYSTEM*]$SYSTEM_TIMER truncated to $SYSTEM_TIME
```

i.e. the UI's `$SYSTEM_TIMER` is truncated to `$SYSTEM_TIME`. ROBOGUIDE's MotionPRO Service Tools
read the same thing, `$SYSTEM_TIME[{0}].RUN_TOT`.

So the data was in the backup all along; it was unreachable because `SYSVARS.SV` is binary and needs
`kconvars` to become text. In converted output the counter is present **445 / 445** converted samples
— a general capability, not a quirk of one machine.

**Unit is minutes, not seconds.** Establish it by differencing, never by assumption: take two backups
of one robot and divide the counter delta by the calendar days between them. Three robots over two
windows (133 days and 401 days) all grew ≈1400/day. As minutes that is ≈23.3 h/day — a three-shift
line's powered-on time, plausible. As seconds it would be 23 minutes/day, which cannot be right.
Several robots on one line show nearly identical growth, consistent with the whole line being
switched on and off together.

## Solution

### Step 1 — Copy the file to a lowercase name

`kconvars` requires the input filename in lowercase. A case mismatch shows up as **exit 6**.
Backups contain both spellings (`SYSVARS.SV` and `sysvars.sv`), so make the extraction script accept
either.

```powershell
Copy-Item SYSVARS.SV .\sysvars.sv -Force
```

### Step 2 — Convert with kconvars from PowerShell

Call it from PowerShell, not Git Bash — under Git Bash/MSYS2 the tool segfaults.

```powershell
& kconvars.exe sysvars.sv sysvars_out.txt
```

### Step 3 — Read the counter out of the converted text

```powershell
Select-String -Path sysvars_out.txt -Pattern '\$SYSTEM_TIME\[1\]\.RUN_TOT'
```

Equivalent with grep once the file is text: search for the literal `$SYSTEM_TIME[1].RUN_TOT`.
If a `converted/` directory already holds `sysvars_out.txt`, read it directly instead of converting
again — the conversion is the expensive step over hundreds of backups.

### Step 4 — Calibrate the unit per fleet, once

Take two backups of the same robot, compute `delta / calendar_days`, and check the daily rate against
the line's real on-hours. Do this before reporting any utilization figure.

## Verification

- Every converted sample carries the counter: **445/445** converted `sysvars_out.txt` files contain
  `RUN_TOT`. Absence in a sample would mean a failed conversion, not a missing capability.
- Unit: three robots, two windows (133 days / 401 days), all ≈1400/day → ≈23.3 h/day as minutes,
  which matches a three-shift line; the seconds reading (23 min/day) is discarded.
- Cross-check against a source of truth: a ROBOGUIDE workcell's `SavePoints` `SYSVARS.SV` carries the
  same `RUN_TOT` as the real robot backup it came from.
- Liveness: in `AutoSave` snapshots of a virtual controller, `PWR_TOT` grows while `RUN_TOT` stays
  put — so the counter tracks running, not wall-clock or power-on.

## Notes

- **Do not over-claim.** `RUN_TOT` was measured **larger** than `SRV_TOT` on the same robot
  (1234559 vs 1202157), which contradicts reading RUN as a subset of "servo powered". FANUC's RUN
  accounting is not SRV plus something; treat them as independent counters. The exact semantics of
  `SHM_TOT` could not be confirmed from the binary.
- Conversion failure modes (exit 6, Git Bash segfault, `robot.ini`) are covered separately in
  `lessons/contrib/fanuc-backup-payload-extraction.md`; this lesson is about *which* variable to read
  and in what unit.
