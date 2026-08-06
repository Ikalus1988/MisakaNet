---
title: "FANUC Robot Program Inspection Methodology — Systematic Check Guide"
domain: "fanuc"
subdomain: "quality"
tags: ["inspection", "checklist", "program-review", "signal-check", "collision-zone", "fine-point", "quality"]
status: "published"
source: "internal-training"
confidence: "0.9"
created: "2026-07-14"
---

## Problem

Robot programs need systematic inspection before production to catch signal mapping errors, safety violations, and logic bugs. Without a structured methodology, inspectors miss critical issues or check inconsistently across different robots.

## Solution

### Inspection Categories

#### 1. Signal Check (All Robots)

Verify all DI/DO/GI/GO signals against the configuration standard:

```
Signal ranges:
  DIDO-PLC:        1-512        (PLC communication)
  DIDO-Connection:  513-2648     (ISV vision, etc.)
  DIDO-Tool:        2649-4096    (end effector tools)
```

For each signal:
- Verify signal number matches configuration standard
- Verify signal name matches function
- Flag undefined signals with suggested purpose

#### 2. Collision Zone FINE Point Check

**Critical safety check**: The motion command BEFORE releasing a collision zone must use FINE positioning (not CNT).

Search pattern:
```
Search: "CollZone Release" or "CollZone, Release"
For each match:
  → Find the last motion command BEFORE the release
  → Verify it uses FINE (not CNT50, CNT100, etc.)
```

Entering a collision zone (Request) does NOT require FINE — only exiting (Release) does.

#### 3. Program Logic Check

**Initialization sequence:**
- TIMER_START present at program start
- MI01_CMN Init call present
- Proper HOME position setup

**Decision Code handling:**
- WAIT GI[5] present for decision code
- SELECT logic for multi-path branching
- All branches lead to valid programs

**Tool change check:**
- TIP_CHECK call present where needed
- Tool change sequence correct (dock/undock pairs)

**End sequence:**
- MOVE_HOME at program end
- TIMER_STOP at program end
- Proper signal cleanup

#### 4. Fixture Check

```
Search: "Fixture IN" → verify corresponding "Fixture OUT"
For each fixture:
  → IN/OUT must be paired
  → IN before entering work area
  → OUT after leaving work area
```

#### 5. Application-Specific Check

**Spot welding:**
- SPOT instruction parameters (SD/P/t/S/ED)
- SPOT instruction must be at FINE point
- Non-weld motions can use CNT

**Gluing:**
- Speed between SS[1] and SE ≤ 500mm/sec
- SS[1] marker present at glue start
- SE marker present at glue end
- GO[22] parameter for glue switching

**SPR (Self-Piercing Rivet):**
- RivetNo./NextRivetNo./GunOpen parameters correct
- MI14_SPR instruction at FINE point
- Magazine refill signal DI[1180] checked

### Inspection Report Template

```markdown
## Inspection Summary
| Category | Items | Passed | Rate |
|----------|-------|--------|------|
| Signal Check | X | X | X% |
| Collision Zone FINE | X | X | X% |
| Application Check | X | X | X% |
| Program Logic | X | X | X% |
| **Total** | **X** | **X** | **X%** |

## Issues Found
| # | Issue | Location | Severity |
|---|-------|----------|----------|
| 1 | ... | Line XX | Low/Med/High |
```

### Program Naming Convention

```
Connection: RobotID_CarModel_ProcessOrder_Process_WorkStation
Example: UB030R01_MS11_01_PICK_JR1

Action: RobotID_ToolID_Process_ToolID
Example: UB030R01_MS11_01_WELD_JR1
```

## Verification

1. Run signal check on a known-good program — should pass 100%
2. Intentionally change a FINE to CNT before CollZone Release — should be caught
3. Remove a Fixture OUT call — should be flagged as missing pair
4. Run full inspection on a new program — verify all categories checked

## Notes

- Always check collision zone FINE points first — this is the most common safety issue
- Signal definitions change between projects — always use the current configuration standard
- Program logic checks should be automated where possible (HTML checker tool)
- Inspection results should be documented for traceability
