---
domain: "fanuc"
title: "FANUC ROBOGUIDE FRVRC auto backup fails on every restart — FILE-077 / FILE-079 / FILE-031"
tags:
  - "fanuc"
  - "roboguide"
  - "frvrc"
  - "auto-backup"
  - "system-variable"
  - "file-077"
  - "file-031"
  - "virtual-controller"
status: "published"
evidence_level: "E1"
created: "2026-10-17"
updated: "2026-10-17"
source: "intake-3309"
summary_plain: "Auto backup fails on every virtual-controller boot because the configured device FRA: is not a legal path."
trigger: "FILE-077 Auto backup start (FRA:\\) FILE-079 Error Auto backup FILE-031 Illegal path name"
verify: "After a restart the FILE-077 / FILE-079 / FILE-031 counts in <workcell>/Robot_1/logfile.txt stop growing, and reading [*SYSTEM*]$AUTOBACKUP_T.$ENABLE returns FALSE/OFF."
provenance:
  source: "intake"
  issue: "#3309"
  contributor: "claude-code"
  note: "FRVRC V9.40 / ROBOGUIDE V9.40179.0.4; structure read from <FRVRC Media>/<version>/product/j545/tpatbdef.sv"
---

## Problem

A FANUC ROBOGUIDE virtual robot controller (FRVRC) tries to auto-backup on every
startup and always fails. Each cold start leaves a fixed triplet in
`<workcell>/Robot_1/logfile.txt`:

```
FILE-077 Auto backup start (FRA:\)
FILE-079 Error Auto backup
FILE-031 Illegal path name
```

The signal is the **group of three**, with the target device shown as `FRA:\` inside
`FILE-077`. One cold start in the reported baseline produced `F077=1 / F079=1 / F031=1`.

The failure is not just noise. Retrying the backup amplifies socket pressure, and when a
separate terminal-security injection conflict is also present on the host (see
`fanuc-rgcore-hang-endpoint-security-injection`), the failed backup is followed by a
PMON → TP reconnect storm and a `frsock.dll` crash.

## Root Cause

FANUC option **J545 (Automatic Backup)** is controlled by the system variable
`[*SYSTEM*]$AUTOBACKUP_T`. Its `$DEVICE` field is set to `FRA:`, and that target is
**not a legal path** in the current virtual-controller configuration — hence
`FILE-031 Illegal path name`. Auto backup starts (`FILE-077`), cannot open the
destination, and aborts (`FILE-079`).

The structure is readable from the product media definition file, so it does not have to
be guessed:

```
<FRVRC Media>/<version>/product/j545/tpatbdef.sv

[*SYSTEM*]$AUTOBACKUP_T
  ├─ $ENABLE      ← master switch
  ├─ $DEVICE      ← backup destination device, default FRA:
  ├─ $TIME / $INTERVAL
  ├─ $OFF_COUNT / $DEL_LOG / $LOG / $LAST_ATB
  └─ ...
```

The UI string file `product/j545/tpfatbeg.tx` confirms the on-controller options:
`Auto Backup`, `DISABLE`/`ENABLE`, and a `[ TYPE ]` selector for the destination device
(`FR A:` / `Mem card (MC)` / `USB Disk (UD1)`).

**Do not confuse this with a missing-file cause.** Another FANUC experience blames backup
failure on a missing `PNIO.SV`. Here `PNIO.SV` is also absent, but the actual error is an
illegal *path*, not a missing *file*. The two failure modes have different evidence and
must not be merged.

## Solution

Pick one of the two fixes.

**A. Disable automatic backup (recommended — smallest change).**

Set `[*SYSTEM*]$AUTOBACKUP_T.$ENABLE` to `FALSE` / `OFF`. Two ways in:

1. **ROBOGUIDE workcell tree →「Variables」node** — edit the system variable directly and
   never touch the teach pendant. Use this path when pendant operation itself is a known
   crash trigger.
2. Teach pendant: `MENU` → `6 SETUP` → `Auto Backup` → `DISABLE`.

**B. Point it at a legal destination.**

Change `$DEVICE` from `FRA:` to an available device. In the UI, `[ TYPE ]` switches to
`Mem card (MC)` or `USB Disk (UD1)`. Whether MC/UD1 are actually usable on a virtual
controller has to be verified per setup.

## Verification

Failing state — the triplet is present with a non-zero count:

```powershell
Select-String -Path ".\Robot_1\logfile.txt" -Pattern "FILE-077|FILE-079|FILE-031"
```

Fixed state:

- In the same `logfile.txt`, the `FILE-077` / `FILE-079` / `FILE-031` counts **stop
  growing** after a restart (they stay at their previous value).
- If `$DEVICE` was changed, the device name inside the `FILE-077` parentheses changes and
  is no longer followed by `FILE-079` / `FILE-031`.
- The variable browser shows `[*SYSTEM*]$AUTOBACKUP_T.$ENABLE` as `FALSE` / `OFF`.

## Notes

- The definition file and UI strings live under
  `<FRVRC Media>/<version>/product/j545/` (`tpatbdef.sv`, `tpfatbeg.tx`); read them rather
  than guessing the variable layout.
- Reported against FRVRC V9.40 / ROBOGUIDE V9.40179.0.4.
- Related: `fanuc-backup-restore-guide` (backup types) and
  `fanuc-rgcore-hang-endpoint-security-injection` (the injection-conflict failure mode that
  this backup failure can precede).
