---
title: "A .cmd with non-ASCII comments emits a phantom \"is not recognized\" command: chcp inside the file is already too late"
domain: "windows"
tags:
  - "windows"
  - "batch"
  - "cmd"
  - "encoding"
  - "codepage"
  - "chcp"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4299"
summary_plain: "A batch wrapper ran correctly (exit code 0, it launched what it should) but wrote this to stderr on every single…"
trigger: "A .cmd with non-ASCII comments emits a phantom \"is not recognized\" command: chcp inside the file is already too late. A batch wrapper ran correctly (exit code…"
verify: "1) Re-run the wrapper with stdout and stderr redirected to files: the exit code is unchanged and the stderr file is empty. 2) The .cmd contains zero non-ASCII bytes - e.g…"
provenance:
  issue: "#4299"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A batch wrapper ran correctly (exit code 0, it launched what it should) but wrote this to stderr on every single run://[REDACTED:url_credential]@host off
    chcp 65001 >nul
    rem <Chinese comment>
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0some-script.ps1"

Because the wrapper still worked, the stray line reads as harmless noise - and it is easy to blame it on a UTF-8 BOM. It is not: the first three bytes here were 40 65 63 ("@ec"), i.e. no BOM at all.

## Root Cause

cmd.exe parses a .bat/.cmd file with the console's *current* code page. `chcp` is just another line in that file, so it only changes the code page once it executes - the parser has already been decoding, and keeps decoding, the file's bytes as though they were in the system ANSI/OEM code page (936/GBK on a Chinese Windows, 1252 on Western ones).

UTF-8 encoded Chinese comments therefore decode into garbage. When the resulting byte sequence maps onto a character cmd treats as meaningful, the line splits and the fragment is executed as a command - producing a phantom "is not recognized" error whose name is mojibake. Non-ASCII `rem` lines are exactly as dangerous as non-ASCII commands: the comment is only a comment if it is parsed as a comment.

## Fix

Keep .bat/.cmd files pure ASCII - no non-ASCII comments, no non-ASCII text in echo lines.

    @echo off
    chcp 65001 >nul
    rem Launch the helper and pass the arguments through.
    rem Keep this file pure ASCII: cmd parses it with the system code page
    rem before chcp takes effect, so non-ASCII here yields bogus command errors.
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0some-script.ps1"
    if errorlevel 1 pause

Move every human-readable message and all non-ASCII output into the script the wrapper calls, and let that script own its encoding (for PowerShell, save it as UTF-8 with BOM). Do not try to fix it by adding a BOM to the .cmd - that only adds a different phantom error.

## Verification

1) Re-run the wrapper with stdout and stderr redirected to files: the exit code is unchanged and the stderr file is empty.
2) The .cmd contains zero non-ASCII bytes - e.g. `[regex]::Matches((Get-Content -Raw file.cmd), '[^\x00-\x7F]').Count` returns 0.
3) The wrapped output still shows Chinese correctly (it now comes from the child process after chcp, not from the batch text).
