---
title: "PowerShell $home is read-only: the assignment errors, then later commands silently use the old value"
domain: "windows"
tags:
  - "powershell"
  - "automatic-variables"
  - "readonly"
  - "gotcha"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4289"
summary_plain: "A script sets a convenience variable named $home (the same trap exists for $host, $pwd, $profile, $input, $args)."
trigger: "PowerShell $home is read-only: the assignment errors, then later commands silently use the old value. A script sets a convenience variable named $home (the…"
verify: "1) `$home='x'` prints the WriteError. 2) (Get-Item variable:home).Options includes ReadOnly / Constant. 3) After renaming, the variable returns the intended path and the command lists the right…"
provenance:
  issue: "#4289"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A script sets a convenience variable named $home (the same trap exists for $host, $pwd, $profile, $input, $args). PowerShell prints:

    WriteError: Cannot overwrite variable HOME because it is read-only or constant.

and the pipeline continues. The next command still resolves $home to the predefined value, so it silently reads the wrong path and returns a plausible but wrong result - for example listing the user profile root instead of the intended data directory.

## Root Cause

$HOME and several other names are predefined automatic variables. Assigning one raises a non-terminating error, which stops nothing unless $ErrorActionPreference is Stop. Downstream commands do not fail; they just use the unchanged automatic value.

## Fix

Pick a name outside the automatic set ($appHome, $dshHome, ...). For a home directory use $env:USERPROFILE. When the output must be trusted, either set $ErrorActionPreference='Stop' or scan for WriteError before relying on later commands.

## Verification

1) `$home='x'` prints the WriteError.
2) (Get-Item variable:home).Options includes ReadOnly / Constant.
3) After renaming, the variable returns the intended path and the command lists the right directory.
