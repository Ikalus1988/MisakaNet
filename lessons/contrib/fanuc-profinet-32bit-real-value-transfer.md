---
title: "FANUC Profinet 32-bit Real Value Transfer Without KAREL"
domain: "fanuc"
tags: ["profinet", "real-value", "32-bit", "gi-go", "plc-communication", "scara"]
status: "published"
source: "robot-forum.com"
subdomain: "profinet"
confidence: "0.85"
created: "2026-07-01"
verified_date: ""
domain_expert: ""
---

## Problem

SCARA 12iA + R-30iB Compact Plus needs to send/receive 32-bit real values via Profinet, but GI/GO are limited to 16-bit integer groups. KAREL is not available.

## Root Cause

FANUC TP register I/O (GI/GO) operates on 16-bit integers only. There are no bitwise operators in TP, and IEEE-754 binary conversion requires bit-level manipulation that TP cannot do natively.

## Solution

Use DIV/MOD word-splitting with a scaling factor to pack two 16-bit words into a 32-bit real value.

### Sending (Robot → PLC)

```fanuc
R[1:real] = 123.456
R[2:scaled] = ROUND(R[1] * 1000)
R[3:low] = MOD(R[2], 65536)
R[4:high] = (R[2] - R[3]) / 65536
GO[1] = R[3]
GO[2] = R[4]
```

### Receiving (PLC → Robot)

```fanuc
R[3:low] = GI[1]
R[4:high] = GI[2]
R[2:scaled] = R[4] * 65536 + R[3]
R[1:real] = R[2] / 1000.0
```

Key value: 65536 = 2^16, the 16-bit boundary.

### Stopping Robot on DI Signal

| Method | Use Case | Notes |
|--------|----------|-------|
| HOLD (UOP input) | Pause and resume | Recommended. HOLD=FALSE stops, TRUE resumes |
| IMSTP | Emergency stop | Immediate, requires restart |
| Speed 0 | Slow stop | Unreliable, Speed+ button overrides |

## Verification

1. Send a known real value (e.g., 123.456) from robot
2. Verify PLC receives correct high/low words
3. PLC sends back, robot reconstructs: `abs(received - original) < 0.001`
4. Test with negative values and edge cases near 32767

## Notes

- Large integers in registers may overflow — adjust scaling factor if range exceeds ±32.767
- PLC must implement the inverse calculation
- If precision allows, prefer 16-bit direct transfer to simplify architecture
- Source: https://www.robot-forum.com/robotforum/thread/55026/
