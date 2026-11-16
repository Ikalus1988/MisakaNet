---
title: "FANUC robot controller alarm pair INTP-222/INTP-248 + INTP-280 \"Application data"
domain: "fanuc"
tags:
  - "fanuc"
  - "robot"
  - "controller"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4857"
summary_plain: "FANUC robot controller alarm pair INTP-222/INTP-248 + INTP-280 \"Application data mismatch\" (应用软体资料不匹配) at a CALL/MACRO…"
trigger: "FANUC robot controller alarm pair INTP-222/INTP-248 + INTP-280 \"Application data. mismatch\" (应用软体资料不匹配) at a CALL/MACRO statement to an existing TP program."
verify: "Same CALL statement executes from both calling programs without INTP-222/INTP-248+INTP-280; alarm log clear."
provenance:
  issue: "#4857"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

FANUC robot controller alarm pair INTP-222/INTP-248 + INTP-280 "Application data mismatch" (应用软体资料不匹配) at a CALL/MACRO statement to an existing TP program.

## Root Cause

Per FANUC Robot R-30iA Alarm Code List Operator's Manual (quoted by aggregator faultresolve.com): "The application data of called program is different from that of the original program." Each TP program carries per-program "application data" (the /APPL section of the .LS, edited on the pendant via DETAIL -> NEXT application-data page; e.g. ArcTool/SpotTool process data plus application option flags). The interpreter rejects a CALL/MACRO when the called program's application data does not match the calling program's. Documented trigger: the called program's application option on the DETAIL->Next page set False/differently than the caller (roboterforum.de thread 17870); offline-generated .LS lacking /APPL block loads fine but fails at run/call with the sibling alarm INTP-281 "No application data" (robodk.com forum).

## Fix

Official remedy text: "Please change the structure of program." Concretely: open both caller and callee on the pendant, DETAIL -> NEXT application-data page, make application type/options consistent (or set the missing option True); or add the proper /APPL block to the .LS (copy syntax from a pendant-exported .LS of a working program) and re-LOAD. Verify by running the same CALL from the previously working program and the previously failing one.

## Verification

Same CALL statement executes from both calling programs without INTP-222/INTP-248+INTP-280; alarm log clear.
