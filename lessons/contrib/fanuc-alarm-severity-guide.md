---
title: "FANUC Alarm Severity Levels — Handling and Color Codes"
domain: "fanuc"
subdomain: "troubleshooting"
tags: ["alarm", "severity", "warn", "pause", "stop", "servo", "abort", "system", "troubleshooting"]
status: "published"
source: "internal-training"
confidence: "0.95"
created: "2026-07-14"
---

## Problem

FANUC controllers display alarms with different severity levels, but engineers don't always understand the implications of each level — which ones stop the robot, which cut servo power, and which require immediate action vs. can be deferred.

## Solution

### Alarm Severity Table

| Severity | Program | Robot Motion | Servo Power | Scope |
|----------|---------|--------------|-------------|-------|
| NONE | No stop | No stop | Not cut | ... |
| WARN | No stop | No stop | Not cut | ... |
| PAUSE.L / PAUSE.G | Pause | Decel then stop | Not cut | Local / Global |
| STOP.L / STOP.G | Pause | Decel then stop | Not cut | Local / Global |
| SERVO | Force end | Instant stop | **Cut** | Global |
| ABORT.L / ABORT.G | Force end | Decel then stop | Not cut | Local / Global |
| SERVO2 / SYSTEM | Force end | Instant stop | **Cut** | Global |

### Severity Descriptions

- **WARN**: Warning for minor/non-critical issues. LED does NOT light up.
- **PAUSE**: Pauses program execution, robot stops after completing current motion. Servo stays on.
- **STOP**: Pauses program execution, robot decelerates to stop. Servo stays on.
- **SERVO**: Interrupts or force-ends program, robot stops INSTANTLY, servo power CUT. Most dangerous motion stop.
- **ABORT**: Force-ends program, robot decelerates to stop. Servo stays on.
- **SYSTEM**: System-level critical issue. ALL operations stop.

### Alarm Color Codes

| Color | Severities | Meaning |
|-------|------------|---------|
| White | NONE, WARN | Informational, no action needed |
| Yellow | PAUSE.L/G, STOP.L/G | Caution, check before resuming |
| Red | SERVO, SERVO2, ABORT.L/G, SYSTEM | Critical, investigate immediately |
| Blue | Reset, SYST-026 | System normal startup |

### Common Alarm Codes

**Servo alarms:**
- SRVO-001: Operator panel emergency stop
- SRVO-002: Teach pendant emergency stop
- SRVO-007: External emergency stop
- SRVO-012: Power failure recovery
- SRVO-048: DCS SSO external emergency stop
- SRVO-062: DSP not running

**Program alarms:**
- INTP-127: Power failure detected
- INTP-224: Cannot branch
- MEMO-027: Specified line not found

**System alarms:**
- SYST-026: System normal startup
- SYST-039: T2 operation mode selected
- SYST-212: DCS parameters need application
- SYST-218: DCS function not available for this model

### Alarm Recovery Procedures

1. **Identify**: Read alarm code and severity from TP display
2. **Investigate**: Check alarm history (MENU → Status → Alarm)
3. **Resolve**: Fix root cause (not just reset)
4. **Reset**: Press RESET key after root cause is fixed
5. **Verify**: Confirm servo power restores and robot operates normally

### DCS Safety Alarms

DCS (Dual Check Safety) uses independent dual CPUs to monitor:
- Position limits
- Speed limits
- Joint speed limits

DCS parameters are stored separately from regular parameters. Changing DCS requires 4-digit password (default: 1111).

Stop distance = (Motion speed × Scan time) + Coast distance at power cutoff
- Standard scan time: 8ms
- Safety signal latency: 2ms (DCS I/O), 4ms (PROFINET)

## Verification

1. Trigger a WARN-level alarm — verify robot continues operating
2. Trigger a PAUSE-level alarm — verify robot decelerates gracefully
3. Trigger a SERVO-level alarm — verify servo power is cut immediately
4. Check alarm history after each test — verify correct logging

## Notes

- WARN alarms don't light the LED — easy to miss in production
- SERVO alarms are the most dangerous — instant stop can damage tooling
- Always fix root cause before pressing RESET
- DCS alarms require special handling — DCS parameters are password-protected
- Alarm history is cleared on power cycle — export before shutdown if needed
