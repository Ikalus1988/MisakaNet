---
title: "FANUC Spot Weld Tip Max Wear Amount — sysspot.sv Variable Lookup via kconvars"
domain: "fanuc"
subdomain: "spot-weld"
tags: ["spot-weld", "electrode-wear", "sysspot", "kconvars", "spoteqsetup", "epaf-trgdst", "tip-dress"]
source: "colleague_memory_dump"
status: "published"
confidence: "0.85"
created: "2026-07-16"
verified_date: "2026-07-16"
domain_expert: ""
evidence:
  level: "pre_ingest_reused"
  source_type: "colleague_memory_dump"
  verified_by: "maintainer"
  context: "Distilled from field debugging session. kconvars sysspot.sv parsing path verified as practically useful."
  public_quote_allowed: false
---

## Problem

Need to find the maximum electrode tip wear amount (最大磨损量) for a FANUC spot welding robot. The value is stored in the `sysspot.sv` system variable file, which uses FANUC's proprietary binary format and cannot be read with standard text editors.

## Root Cause

FANUC stores spot welding configuration in `sysspot.sv` (not `sysvars.sv`). This file contains `$SPOTEQSETUP` arrays with electrode parameters. Like other `.sv` files, it requires the `kconvars.exe` tool from WinOLPC to decode the binary format.

Key parameter path:

```
$SPOTEQSETUP[1].$EPAF_TRGDST = 5.00mm  ← 最大磨损量（可动侧电极）
$SPOTEQSETUP[2-5].$EPAF_TRGDST = 5.00mm  ← 其他设备
```

## Fix

### Step 1: Locate the file

```
<backup_dir>/sysspot.sv
```

### Step 2: Convert with kconvars

```bash
kconvars.exe sysspot.sv > sysspot_decoded.txt
```

Note: kconvars requires `robot.ini` in the same directory or parent. If it crashes, check path encoding (non-ASCII paths cause failures).

### Step 3: Find the wear parameter

Search the decoded output for:

```
$SPOTEQSETUP[1].$EPAF_TRGDST
```

This value is the maximum wear amount in mm.

## Verification

- The value should be a positive number (typically 3.0–10.0 mm)
- Multiple `$SPOTEQSETUP[x]` entries exist for multi-gun setups (x = 1–5)
- Cross-check with R[32] (原始电极磨损) and R[33] (当前电极磨损) user registers if available

## Related Parameters

| Parameter | Description |
|---|---|
| `$SPOTEQSETUP[x].$EPAF_TRGDST` | 最大磨损量 (max wear threshold) |
| `$SPOTEQSETUP[x].$TD_LIMIT` | 修磨次数限制 (tip dress count limit) |
| `$SPOTCONFIG.$TD_AFTER_CC` | 焊后修磨 (tip dress after current cycle) |
| `R[32]` | Gun1 原始电极磨损 (original tip wear) |
| `R[33]` | Gun1 当前电极磨损 (current tip wear) |
| `R[36]` | 修磨磨损量 (tip dress wear amount) |

## Important Notes

- **Only max wear amount is in the backup.** Other electrode detection parameters (load margin, electrode speed, pressure calibration) are stored in the weld controller, not in the robot backup.
- `$SPOTEQSETUP` array size depends on the number of guns configured (typically 1–5).
- User registers R[32], R[33], R[36] are runtime values — they change during operation and are not in the backup.

## Related Memories

- [[fanuc-backup-payload-extraction]] — .VR/.SV binary parsing and kconvars usage
- [[reference_dcs_parsing]] — DCS safety configuration parsing
- [[reference_diocfgsv_parsing]] — IO signal configuration parsing
