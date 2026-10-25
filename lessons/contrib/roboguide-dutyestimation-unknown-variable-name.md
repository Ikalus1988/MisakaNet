---
title: "ROBOGUIDE DutyEstimation fails with 'Unknown variable name': the controller does not provide $CP_PARAMGRP"
domain: "fanuc"
tags:
  - "fanuc"
  - "roboguide"
  - "dutyestimation"
  - "system-variables"
  - "cp-paramgrp"
  - "plugin-mismatch"
  - "motor-load"
  - "deceplugin"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "ROBOGUIDE 的电机负载率估算插件初始化报 Unknown variable name，是控制器选项里没有它查询的 $CP_PARAMGRP，不是崩溃。"
trigger: "FRVariablesClass.get_SysVarInteger Unknown variable name DutyEstimation.DECPlugin.msubSetupRobot CP_PARAMGRP"
verify: "Re-run DutyEstimation on the same workcell: no 'Unknown variable name' dialog, grep -r CP_PARAMGRP on the workcell hits, and DutyData is no longer empty."
source: "intake-3243"
provenance:
  issue: "#3243"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# ROBOGUIDE DutyEstimation fails with 'Unknown variable name': the controller does not provide $CP_PARAMGRP

## Problem

Opening a ROBOGUIDE workcell with the DutyEstimation plugin (motor duty / load-rate estimation) raises an
initialisation error. The reported text, verbatim:

```text
FRVariablesClass.get_SysVarInteger Unknown variable name.
```

The stack lands in the plugin's own setup step:

```text
FRMOTIONLib.FRVariablesClass.get_SysVarInteger -> "Unknown variable name"
   at DutyEstimation.DECPlugin.msubSetupRobot
```

ROBOGUIDE otherwise keeps working; it is the load-rate estimation that is unavailable. The reporter's
observations, used as criteria below:

- `grep -r CP_PARAMGRP <workcell>` returns no hit — measured across *all* workcells, not one;
- every `DutyData` directory is empty.

## Root Cause

The plugin reads controller system variables — `$CP_PARAMGRP`, and reportedly `$MAX_AMP_CUR` as well — and
the controller image does not contain `$CP_PARAMGRP` at all. `get_SysVarInteger` therefore answers
"unknown variable name" instead of returning a value, and the plugin's setup step aborts.

The variable is supplied by a software option. The controller's current option set does not include that
option, so this is a **plugin/controller option mismatch**, not a crash, not a corrupted workcell, and not
a parser bug. The report explicitly separates it from the FRVRC / `frsock` / OS-145 crash family: it is an
independent problem.

Why the mismatch, rather than "the plugin is broken": the failing frame is the plugin's setup step that
reads those variables, the variable is absent from the image (zero hits), and no data was ever collected
(`DutyData` empty). A plugin that is installed and starting is a plugin whose code loaded; what is missing
is a controller-side input.

## Solution

1. Dismiss the dialog with OK. It is non-fatal — ROBOGUIDE's other functions keep working, and only duty
   estimation is unavailable.
2. If load-rate estimation is actually needed, install the software option that provides `$CP_PARAMGRP` on
   the virtual controller. Which option that is depends on the controller software version: check the FANUC
   option manual, or ask FANUC support. The option number is **not** in the report — 报料者未给出，需复现确认.
3. Do not start with a plugin reinstall or a workcell re-creation: reinstalling DutyEstimation cannot add a
   variable the controller does not have.

## Verification

Judge in the same workcell, before and after the option install:

1. `grep -r CP_PARAMGRP <workcell>` — no hit before, hit after;
2. the `DutyData` directory — empty before, populated after;
3. the dialog and its stack (`DECPlugin.msubSetupRobot` → `get_SysVarInteger`) — present before, gone after.

The report also names `cmosimg.bin` / `SYSVARS.SV` as where the variable can be looked up once the option
is installed; a hit for `CP_PARAMGRP` there is the controller-side proof.

## Notes

- The option number, the controller software version and the DutyEstimation build are not in the report —
  报料者未给出，需复现确认.
- `$MAX_AMP_CUR` is named in the report as another variable the plugin reads; only `$CP_PARAMGRP` was
  verified absent.
- "Non-fatal" here means "the plugin's setup step failed", not "the controller is unhealthy": a controller
  that lacks an option variable for one plugin is still a valid controller.
