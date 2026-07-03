---
title: "FANUC INTP-102 DETECT JOINT — OLP Whitespace Bug"
domain: "fanuc"
subdomain: "olp"
tags: ["intp-102", "detect-joint", "olp", "robodk", "ls-format", "whitespace", "arc-sensor"]
source: "robot-forum.com"
status: "published"
confidence: "0.9"
created: "2026-07-01"
verified_date: ""
domain_expert: ""
---


## Problem

OLP tool (RoboDK) generates programs with `DETECT JOINT[3,22]` that throw INTP-102 ("Code format is not valid") on the controller. Manually typing the same command on the teach pendant works fine. The .ls file appears visually identical.

Controller: R-2000iC/165F, V9.40P/80, UNIVERSAL SENSOR IF2 (R901)

## Root Cause

The OLP tool inserts extra trailing spaces before the semicolon in .ls file lines. The controller's parser is strict about whitespace in sensor instructions like DETECT JOINT.

Example of the issue:

```
21: DETECT JOINT[3,22]  ;   ← two spaces before semicolon (FAILS)
21: DETECT JOINT[3,22] ;    ← one space before semicolon (OK)
```

## Solution

### Step 1: Compare .ls Files

Extract the .ls from the robot controller (FTP or memory card) and diff against the OLP-generated version:

```bash
diff robot_original.ls olp_generated.ls
```

### Step 2: Fix Trailing Whitespace

Remove extra spaces before semicolons in sensor instructions. The pattern to fix:

```
DETECT JOINT[n,m]  ;   →   DETECT JOINT[n,m] ;
SEARCH ON[n,*,*,*]  ;  →   SEARCH ON[n,*,*,*] ;
SENSOR ON[n,*,*,*]  ;  →   SENSOR ON[n,*,*,*] ;
```

### Step 3: Report to OLP Vendor

File a bug with RoboDK (or your OLP tool) about trailing whitespace in sensor instruction generation.

## Verification

1. Load the fixed .ls file to controller — no INTP-102 error
2. Run the sensor program — DETECT JOINT executes correctly
3. FTP the program back out — confirm no re-introduced whitespace

## Notes

- This is a parser strictness issue, not a logic error
- TP-entered instructions always use exactly one space before semicolons
- OLP tools may have similar issues with other sensor instructions (SEARCH, SENSOR ON/OFF)
- General rule: when OLP-generated programs report format errors, diff the .ls file for whitespace/encoding differences first
- Source: https://www.robot-forum.com/robotforum/thread/55246/
