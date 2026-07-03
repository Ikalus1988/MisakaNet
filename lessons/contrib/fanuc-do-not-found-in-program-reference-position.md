---
title: "FANUC DO Not Found in Program — Check Reference Position"
domain: "fanuc"
subdomain: "troubleshooting"
tags: ["do", "digital-output", "reference-position", "background-logic", "space-function", "search"]
source: "robot-forum.com"
status: "published"
confidence: "0.9"
created: "2026-07-01"
verified_date: ""
domain_expert: "Nation"
---


## Problem

A digital output (e.g., DO[66]) is confirmed active on the robot, but searching all TP programs for "DO[66]" or "DO[" returns zero results. The output is being set somewhere, but not in any visible program code.

## Root Cause

The DO is assigned to a **Reference Position** setting, not to program code. Reference positions can trigger DOs automatically when the robot reaches a configured position — this is configured outside of any TP program.

Other possible sources:
- Background Logic (BG Logic) — not visible in standard program search
- Space Function — position-based DO activation
- Manual Macro (M[] markers)

## Solution

### Step 1: Check Reference Positions

MENU → SETUP → Reference Position

Each reference position can have:
- Position definition (joint or Cartesian)
- DO assignment (which output to activate)
- Condition (within tolerance, etc.)

### Step 2: Check Background Logic

MENU → SETUP → BG Logic

Look for DO assignments in BG Logic programs that run continuously.

### Step 3: Check Space Functions

MENU → SETUP → Space

Space functions can activate DOs based on robot position within defined volumes.

### Step 4: Search All Sources

```fanuc
-- Use program search with broader terms:
-- Search for the DO number in ALL program types
-- Including: TP, KAREL, BG Logic, Macro, Reference Position
```

## Verification

1. Navigate to MENU → SETUP → Reference Position
2. Find the reference position that assigns DO[66]
3. Modify or remove the DO assignment as needed
4. Verify DO[66] behavior changes accordingly

## Notes

- "Solved, close the question" without posting the fix defeats the purpose of a forum — always share the solution
- Reference Position DOs are invisible to standard program text search
- This is a common gotcha for new FANUC users
- Source: https://www.robot-forum.com/robotforum/thread/55076/
