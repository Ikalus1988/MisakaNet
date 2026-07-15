---
title: "FANUC DCS Safety System — Configuration and Stop Modes"
domain: "fanuc"
subdomain: "safety"
tags: ["dcs", "safety", "dual-check", "emergency-stop", "fence", "stop-mode", "safety-io", "iso13849"]
status: "published"
source: "internal-training"
confidence: "0.95"
created: "2026-07-14"
---

## Problem

FANUC DCS (Dual Check Safety) is a critical safety system that uses independent dual CPUs to monitor robot position and speed. Misconfiguration can lead to safety violations or false trips. Engineers need to understand the DCS architecture, stop modes, and safety I/O to configure it correctly.

## Solution

### DCS Overview

- Independent dual-CPU monitoring of motor speed and position
- Dual-circuit power cutoff on detection of speed/position anomalies
- Meets ISO 13849-1 and IEC 61508 requirements
- Default emergency stop password: 1111

### DCS Function Table

| Function | Category | PL/SIL | Description |
|----------|----------|--------|-------------|
| Emergency Stop | Cat 4 | PL e / SIL 3 | Cut drive power on E-stop button (default) |
| Position/Speed Check | Option | Cat 3 / PL d / SIL 2 | Monitor position and speed, cut on exceed |
| Joint Speed Check | Option | Cat 3 / PL d / SIL 2 | Monitor joint speed, cut on exceed |
| Basic Position Check | Option | Cat 3 / PL d / SIL 2 | Monitor Cartesian position, cut on exceed |
| Safety I/O Connection | Option | Cat 4 / PL e / SIL 3 | Operate safety signals |
| External Mode Switch | Option | Cat 4 / PL e / SIL 3 | Replace panel mode switch |
| Device Network Security | Option | Cat 4 / PL e / SIL 3 | Network security slave device |
| Safety PMC | Option | Cat 4 / PL e / SIL 3 | Safety I/O sequence via ladder |
| Additional Axis Servo Off | Option | Cat 4 / PL e / SIL 3 | Cut additional axis motor power |
| Safety I/O Consistency | Default | Cat 4 / PL e / SIL 3 | Cut power on I/O group inconsistency |

### Stop Types

| Type | Description |
|------|-------------|
| P-Stop (Power Stop) | Cut servo power instantly — robot stops immediately |
| C-Stop (Control Stop) | Decelerate then cut servo power — controlled stop |
| Hold | Maintain servo power, decelerate to stop — softest stop |

### Stop Modes

| Mode | E-Stop Button | External E-Stop | Fence Open | SVOFF Input |
|------|---------------|-----------------|------------|-------------|
| A | P-Stop | P-Stop | C-Stop | C-Stop |
| B | P-Stop | P-Stop | P-Stop | P-Stop |
| C | C-Stop | C-Stop | C-Stop | C-Stop |

### Safety I/O Signals

| Signal | Description |
|--------|-------------|
| EES1 / EES2 | External emergency stop input (dual circuit) |
| EAS1 / EAS2 | Fence input (dual circuit) |
| FENCE1 / FENCE2 | Fence signal (single circuit) |
| EMGIN1 / EMGIN2 | External emergency stop (single circuit) |
| SSO[3] / SSO[4] | DCS safety I/O |

### DCS Parameter Management

DCS parameters are stored in separate memory from regular parameters:
- DCSPOS.SV — Position check parameters
- DCSIOC.SV — I/O check parameters
- SYSCIPS.SV — System safety parameters

**To change DCS parameters:**
1. Change setting parameters first
2. Apply to DCS parameters
3. Enter 4-digit password (default: 1111)

### Stop Distance Calculation

```
Stop Distance = (Motion Speed × Scan Time) + Coast Distance at Power Cutoff
```

- Standard scan time: 8ms
- Safety signal latency: 2ms (DCS I/O), 4ms (PROFINET)

### Common DCS Alarms

- SYST-212: DCS parameters need application
- SYST-218: DCS function not available for this model
- SRVO-048: DCS SSO external emergency stop
- SRVO-049: DCS SSO servo disconnect
- SRVO-223: DCS SSO error

## Verification

1. Check DCS parameter file exists: DCSPOS.SV, DCSIOC.SV
2. Verify stop mode matches application requirements (A/B/C)
3. Test E-stop button — should trigger correct stop type per mode
4. Test fence signal — should trigger correct stop type per mode
5. Verify DCS position limits match physical workspace constraints

## Notes

- DCS is a safety-critical system — changes require proper authorization and documentation
- Always backup DCS parameters before modification
- Stop mode B (P-Stop on everything) is the safest but most aggressive
- Stop mode C (C-Stop on everything) is the gentlest but slowest to stop
- PROFINET safety signals have higher latency (4ms) than DCS I/O (2ms)
- DCS parameters are NOT included in regular parameter backup — backup separately
