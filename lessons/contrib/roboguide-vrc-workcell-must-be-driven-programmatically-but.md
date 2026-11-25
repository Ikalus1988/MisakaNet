---
title: "ROBOGUIDE VRC workcell must be driven programmatically, but every netwo"
domain: "fanuc"
tags:
  - "the"
  - "and"
  - "in"
status: "published"
evidence_level: "E1"
created: "2026-11-25"
updated: "2026-11-25"
source: "intake-5797"
summary_plain: "Symptom: ROBOGUIDE VRC workcell must be driven programmatically, but every network channel is dead — HTTP KCL falls…"
trigger: "FRRobot COM IProgram Run memid DISP_E_UNKNOWNNAME, KAREL DELAY hang, zero-distance MOVE TO hang, Formats(9) Item joint readback"
verify: "ConnectEx('localhost') -> IsConnected True; memid-Invoke Run(-1,1,0) on a DELAY-free single-move program -> Formats(9).Item(1..6) matches the target within 0.005 deg."
provenance:
  issue: "#5797"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Symptom: ROBOGUIDE VRC workcell must be driven programmatically, but every network channel is dead — HTTP KCL falls back to the robot homepage, FTP hangs and re-triggers the frsock OS-145 crash chain, the KCL console lands in SMON. The controller GUI itself is healthy and the 3D view renders fine.

## Root Cause

The usable channel is the local COM automation API `FRRobot.FRCRobot` (registered on every ROBOGUIDE install), which never touches the frsock TCP layer that endpoint-security injection kills. Its IDispatch surface has several traps: (1) IProgram.Run is vtable-only — makepy never generates it and GetIDsOfNames('Run') returns DISP_E_UNKNOWNNAME, so it must be called by its typelib memid via IDispatch.Invoke(dispid, lcid, wFlags, *args) — pythoncom's Invoke has NO IID slot (passing one lands a PyIID in the lcid position); (2) Run(StepType, LineNum, Direction) needs StepType=-1 (frStepNone, continuous) — 0 is frStepStatement and runs exactly one statement then stops; (3) joint readback is CurPosition.Group(1, 0).Formats(9).Item(1..6) — IJoint is an indexed container (Item/SetItem by axis number), not an object with .Joint1/.X properties; (4) COM objects are apartment-bound: a worker thread must CoInitialize and create its own Dispatch connection (else RPC_E_DISCONNECTED); (5) KCL errors raise com_error — "Task is not found" from ABORT is normal, and a silent None return does NOT mean failure (verify via Programs enumeration). Additionally the VRC motion layer has quirks: KAREL DELAY never returns (a program parks forever on its first DELAY), a zero-distance MOVE TO hangs forever (start==target), and moves below ~0.05 deg are silently swallowed — plus motion commands get swallowed in storm bursts on machines with the endpoint-security crash chain, where one state per fresh controller boot + retry-until-arrival is the reliable pattern.

## Fix

Drive the controller via win32com.client.Dispatch("FRRobot.FRCRobot") + ConnectEx("localhost", False, 5, 2.0); execute KCL with robot.KCL(cmd, wait) (each command independently try/excepted); run programs by memid Invoke of Run with (-1, 1, 0); read joints via CurPosition.Group(1, 0).Formats(9).Item(i). For pose sequences use one DELAY-free single-move program per state, script-paced: fire -> poll readback until arrival -> capture -> next; order states so every hop is a real >=10 deg move; retry each fire (swallowed moves succeed on refire) and take one state per controller boot when the machine is in a crash-storm phase.

## Verification

ConnectEx('localhost') -> IsConnected True; memid-Invoke Run(-1,1,0) on a DELAY-free single-move program -> Formats(9).Item(1..6) matches the target within 0.005 deg.
