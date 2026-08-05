---
title: "FANUC Payload Estimation — Auto and Manual Load Configuration"
domain: "fanuc"
subdomain: "configuration"
tags: ["payload", "load", "estimation", "tcp", "tool", "mass", "inertia", "center-of-gravity"]
status: "published"
source: "internal-training"
confidence: "0.9"
created: "2026-07-14"
---

## Problem

FANUC robots require accurate payload (load) configuration for safe and precise motion. Incorrect payload settings cause poor motion accuracy, excessive motor load, and can trigger collisions or servo alarms. Engineers need to know how to estimate and configure payloads correctly.

## Solution

### Payload Parameters

Each payload definition includes:
- **Mass**: Weight of end effector + workpiece (kg)
- **Center of gravity**: Position relative to flange (X, Y, Z in mm)
- **Inertia**: Rotational inertia tensor (Ix, Iy, Iz in kg·m²)

### Auto Estimation

The controller can automatically estimate payload parameters by executing predefined motions:

```
SETUP → Payload Estimation → Select estimation method → Execute → Save results
```

Steps:
1. Install end effector on robot
2. Navigate to payload estimation function
3. Select estimation method (typically 4-point or 6-point)
4. Robot executes calibration motions
5. System calculates mass, COG, and inertia
6. Review and save results

### Manual Configuration

When payload parameters are already known:

```
MENU → Setup → Frames → Payload → Select payload number → Enter parameters
```

### PAYLOAD Command in Programs

Set payload in TP programs using the PAYLOAD instruction:

```fanuc
! Set payload 1 (e.g., weld gun) ;
PAYLOAD[1:WeldGun] ;

! Set payload 3 (e.g., gripper) ;
PAYLOAD[3:Gripper] ;
```

### PAYLOAD Numbering Rules

- Number payloads sequentially by process order (small to large)
- PAYLOAD[n] should match UTOOL_NUM value
- Each process program must have a PAYLOAD declaration
- Special case: Tool change uses PAYLOAD[10] with UTOOL_NUM=29

### PAYLOAD-UTOOL Correspondence

| Configuration | Rule |
|---------------|------|
| PAYLOAD[n] | Load identifier, n = number |
| UTOOL_NUM | Tool coordinate number |
| Relationship | PAYLOAD[n] number n should match UTOOL_NUM value |

Examples:
- SPR process: `PAYLOAD[1:SPR_01]` + `UTOOL_NUM=1` ✓
- Tool change: `PAYLOAD[10:TOOL CHANGE]` + `UTOOL_NUM=29` ✓

### When to Re-estimate

- New project commissioning
- End effector modification or replacement
- Workpiece weight changes significantly
- After collision or impact event
- Collision detection sensitivity issues

## Verification

1. Check payload mass matches physical measurement (±10%)
2. Verify COG position is reasonable for the tool geometry
3. Run robot at low speed (10%) with new payload — no excessive vibration
4. Check motor current is within normal range during motion
5. Verify collision detection works correctly with new payload

## Notes

- Payload estimation affects collision detection sensitivity — always re-calibrate after changes
- Inertia estimation is critical for high-speed applications
- For tools with variable payload (e.g., carrying different workpieces), use the maximum expected payload
- The robot must be in a safe position during estimation — clear the work area
- Payload settings are stored per-controller, not per-program
