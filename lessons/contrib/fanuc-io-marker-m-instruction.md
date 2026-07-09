---
title: "FANUC IO Marker M[] Instruction — Background Logic Alternative"
domain: "fanuc"
tags: ["marker", "m-register", "io", "background-logic", "handling-tool", "vass"]
status: "published"
source: "robot-forum.com"
subdomain: "tp-programming"
confidence: "0.85"
created: "2026-07-01"
verified_date: ""
domain_expert: "cattmampbell"
---

## Problem

The M[] option appears in the I/O replace menu but is undocumented in standard TP programming guides. Users don't know what it does or when to use it.

## Root Cause

M[] is a Marker register — a background-logic-like flag system built into FANUC HandlingTool. It evaluates Boolean expressions continuously without BG Logic. Disabled by default: `$MIX_LOGIC.$USE_MKR=FALSE`.

## Solution

### Enable Markers

```
Set $MIX_LOGIC.$USE_MKR = TRUE
```

A new Marker option appears in MENU → I/O.

### Usage

```fanuc
M[1] = (DI[1] AND DI[2])
```

This expression runs in the background continuously until cleared or overwritten. No BG Logic task needed.

### VASS Standard Use Cases (VW/Audi/SEAT/Škoda)

Markers are used extensively in VASS (Volkswagen Automotive Standard) for:

| Category | Examples |
|----------|----------|
| Docking | Docking Stand 1 Occupied/Empty, Tool 1 Docked/Undocked |
| Handling | Clamp 1 Open/Close, Magnet 1 On/Off, Vacuum 1 Blow/Suck |
| Machine Safety | Air OK, Water OK, Spot Welding Gun OK |

Used with `TIMER BEFORE`, `POINT LOGIC (P-SPS)`, and `TC ONLINE` instructions.

### Practical Example: Analog Sensor to Digital Input

```fanuc
-- Map analog sensor to marker for MH valve input
M[1] = (AI[1] > R[1])  -- R[1] = closed threshold per part type
-- Use M[1] as input in MH valve config instead of DI
```

This is useful when "closed" distance varies by part type — set threshold in R[1], MH valve config stays constant.

## Verification

1. Set `$MIX_LOGIC.$USE_MKR = TRUE`
2. Create `M[1] = (DI[1] AND DI[2])` in a program
3. Toggle DI[1] and DI[2] — M[1] updates automatically in background
4. Check MENU → I/O → Marker shows the correct state

## Notes

- Markers are specific to HandlingTool option — not available on all controllers
- Advantage over BG Logic: no separate task, no PR/register restrictions
- Disadvantage: limited to Boolean expressions, no motion control
- Originally from KUKA, adopted by VW into FANUC standard
- Source: https://www.robot-forum.com/robotforum/thread/54934/
