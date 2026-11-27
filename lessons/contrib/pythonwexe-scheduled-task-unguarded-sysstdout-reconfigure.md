---
title: "pythonw.exe + scheduled task: unguarded sys.stdout reconfigure at module top lev"
domain: "windows"
tags:
  - "before"
  - "pythonw"
  - "exe"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-3969"
summary_plain: "pythonw.exe + scheduled task: unguarded sys.stdout reconfigure at module top level crashes silently with exit…"
trigger: "pythonw.exe + scheduled task: unguarded sys.stdout reconfigure at module top lev. level crashes silently with exit 0x80070001."
verify: "Three-part proof: (1) same script under python.exe exits 0; (2) Start-Process pythonw WITH stdio redirection exits 0 (handles exist); (3) Task event Id=201 shows that action failing 0x80070001 every…"
provenance:
  issue: "#3969"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

pythonw.exe + scheduled task: unguarded sys.stdout reconfigure at module top level crashes silently with exit 0x80070001. Windows Task Scheduler action switched from python.exe to pythonw.exe (to avoid flashing a console) starts exiting instantly with no output: pythonw has no console, sys.stdout is None, AttributeError at startup, exit code 1 shown as 0x80070001/2147942401 in event Id=201; pythonw swallows the traceback so it looks like "no error, task just does nothing". print()-only scripts keep working because print to None is a silent no-op.

## Root Cause

pythonw runs without a console so sys.stdout/.buffer is None; console-assuming code crashes before any logging, traceback suppressed.

## Fix

Guard every stdout reshape at module top level: `if sys.stdout is not None and hasattr(sys.stdout, "buffer"):` before TextIOWrapper; `if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):` before reconfigure. Keep pythonw as the task action (reverting to python.exe flashes a console on every trigger); never rely on print-only logging under pythonw — log() must also write to a file.

## Verification

Three-part proof: (1) same script under python.exe exits 0; (2) Start-Process pythonw WITH stdio redirection exits 0 (handles exist); (3) Task event Id=201 shows that action failing 0x80070001 every run while the script's product mtimes freeze and other steps of the same task refresh normally.
