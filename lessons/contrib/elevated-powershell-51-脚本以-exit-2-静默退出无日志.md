---
title: "Elevated PowerShell 5.1 script exits 2 with no log when it contains a non-ASCII string literal"
domain: "windows"
tags:
  - "powershell"
  - "windows"
  - "encoding"
  - "gbk"
  - "elevation"
  - "mojibake"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4528"
summary_plain: "On Windows, an elevated PowerShell 5.1 script (launched via `Start-Process -Verb 'RunAs' -Wait`) exits with code 2 and…"
trigger: "Elevated PowerShell 5.1 script exits 2 with no log when it contains a non-ASCII string literal. On Windows, an elevated PowerShell 5.1 script (launched via…"
verify: "After changing only the string literals (no logic change), the same elevated invocation `Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',<script> -Verb 'RunAs'…"
provenance:
  issue: "#4528"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

On Windows, an elevated PowerShell 5.1 script (launched via `Start-Process -Verb 'RunAs' -Wait`) exits with code 2 and writes no log at all, when the `.ps1` is UTF-8 without BOM and contains any non-ASCII string literal — here a log path under a Chinese-named directory (`<PATH>). The same script runs fine when not elevated, which makes it look like an elevation/UAC problem. A 0-byte or missing log is the only evidence.

## Root Cause

PowerShell 5.1 decodes a BOM-less `.ps1` with the system ANSI code page (GBK/936 on this host), not UTF-8. A non-ASCII *comment* usually still parses (it becomes mojibake but stays a comment), but a non-ASCII *string literal* is mangled into different characters, so the path it names no longer exists and the script dies before producing any output. The failure is a runtime error inside a script that has no transcript and no visible console (elevated + hidden window), so nothing surfaces except the exit code.

## Fix

Two working fixes. (1) Rewrite the script ASCII-only: English log text, and no Chinese in literals either (paths, file names); derive directories from `$PSScriptRoot` instead of hard-coding them — e.g. `$log = Join-Path $PSScriptRoot 'move.log'`. (2) Or save the `.ps1` as UTF-8 **with BOM**, which PowerShell 5.1 honours. Prefer (1) for scripts that may be edited on other machines: it removes the encoding question entirely.

## Verification

After changing only the string literals (no logic change), the same elevated invocation `Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',<script> -Verb 'RunAs' -Wait` returned exit 0 and produced the log with its expected content (`copy ok size=1194MB`). Before the change the identical command returned exit 2 and no log file was created.
