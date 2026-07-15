---
title: "FANUC TCP and Tool Configuration — Standards for Automotive Applications"
domain: "fanuc"
subdomain: "configuration"
tags: ["tcp", "tool", "utool", "uframe", "payload", "coordinate", "automotive", "welding", "gluing", "riveting"]
status: "published"
source: "internal-training"
confidence: "0.9"
created: "2026-07-14"
---

## Problem

In automotive robot applications, TCP (Tool Center Point) and tool configuration must follow specific standards for each process type (spot welding, gluing, SPR, etc.). Incorrect TCP direction or tool numbering causes program errors, quality issues, and safety problems.

## Solution

### TCP Calibration Method

- **Handheld tools**: 6-point TCP with ZX measurement method
  - Rotation amplitude > 90°
  - Traverse distance > 50mm
- **Fixed tools** (fixed gluing, floor welding): Use RTCP (Remote TCP)
- **TCP direction**: Right-hand rule convention

### TCP Position by Process

| Process | TCP Position |
|---------|--------------|
| Spot welding | Servo gun static arm tip |
| SPR riveting | Static arm tip |
| Gluing | Glue nozzle tip (Z offset = nozzle diameter × 1.5) |
| Material handling | Fixture locating pin |
| Stud welding | Spiral surface center |
| Laser brazing | Laser focal point |
| Hemming | Roll wheel lowest point (Z+ toward part, X+ along rolling direction) |

### TCP Direction Standards

**Spot welding gun (both handheld and fixed):**
- Z+: Static arm → moving arm direction (gun open/close direction)
- X+: Along gun axis (from gun root → static arm tip)
- Handheld and fixed gun TCP directions are IDENTICAL

**Hemming tool:**
- Z+: Toward part (pressure direction)
- X+: Along rolling direction

**Stud welding tool:**
- Z+: Along stud axis direction

**Laser brazing:**
- Z+: Along laser beam direction

**Gluing nozzle:**
- Z+: Along nozzle axis direction

**External/remote tool (floor-mounted):**
- Same direction convention as handheld tools
- Z+ toward part, X+ forward

### RTCP (Remote TCP) Toggle

For floor-mounted tools (spot welding machines, glue nozzles, spindles):
```
FUNCTION menu → TOGGLE REMOTE TOOL
```

### UTOOL/UFRAME/PAYLOAD Numbering

- Number by process order: small to large
- Each fixture must have its own base frame / user frame
- Set in operational sequence
- Rack base frame origin: on tower rack locating pin
- XY plane same as pad plane, X+ toward rack interior, Z+ up

### Tool Coordinate Setup

**3-point TCP calibration:**
1. Select 3 different orientations pointing to same point
2. Controller calculates TCP position
3. UTOOL_NUM=1 selects tool number

**6-point TCP calibration (with orientation):**
1. 3 points define TCP position
2. 3 points define tool direction (X/Z axes)

**Direct input:**
```
MENU → Setup → Frames → Tool Frame → Enter X, Y, Z, W, P, R offsets
```

### User Frame Setup

**3-point method:**
1. Origin point
2. X direction point
3. Y direction point (doesn't need to be exactly on Y axis)

**4-point method:**
1. Origin
2. X direction
3. Y direction
4. Z direction (more precise)

### System Variables

| Variable | Description |
|----------|-------------|
| $MNUTOOL[1,i] | Tool coordinate data (i=1-10) |
| $MNUTOOLNUM[group] | Current tool number |
| $MNUFRAME[1,i] | User coordinate data (i=1-9) |
| $MNUFRAMENUM[1] | Current user frame number |
| $USE_UFRAME | Whether user frame is active |

### In-Program Tool/Frame Selection

```fanuc
UTOOL_NUM=1          ! Select tool 1
UTOOL_NUM=R[1]       ! Indirect selection via register
UFRAME_NUM=1         ! Select user frame 1
UFRAME_NUM=R[1]      ! Indirect selection via register
```

### Coordinate System Switch (Manual Jog)

Press COORD key to cycle: JOINT → JGFRM → WORLD → TOOL → USER

## Verification

1. Verify TCP position matches expected tool geometry
2. Verify TCP direction follows right-hand rule for the process type
3. Run robot at 10% speed with new TCP — verify motion is correct
4. Verify UTOOL_NUM matches PAYLOAD number in program
5. Verify user frame origin is on fixture locating pin

## Notes

- TCP direction for fixed welding guns is the SAME as handheld — this is a common mistake
- RTCP must be disabled for non-motion applications
- Never use Base[0]/UFrame[0] for fixtures
- Process points (FDS, appearance welds, SPR, etc.) must use FINE positioning
- Glue nozzle Z offset is typically nozzle diameter × 1.5
