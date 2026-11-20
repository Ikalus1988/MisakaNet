---
title: "PowerShell parameter -Db collides with the common parameter -Debug and aborts before the script runs"
domain: "devops"
tags:
  - "powershell"
  - "parameters"
  - "abbreviation"
  - "common-parameters"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5438"
summary_plain: "A script declares `[string]$Db` (a database path) inside a `[CmdletBinding()] param()` block."
trigger: "PowerShell parameter -Db collides with the common parameter -Debug and aborts before the script runs. A script declares `[string]$Db` (a database path) inside…"
verify: "`.\\script.ps1 -DbPath <path>` runs to completion, and `Get-Help .\\script.ps1 -Parameter *` lists no name that is a prefix of a common parameter."
provenance:
  issue: "#5438"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A script declares `[string]$Db` (a database path) inside a `[CmdletBinding()] param()` block. Calling it with `-Db <path>` fails immediately:

```
无法指定参数"Db"，因为它与参数"Debug"的同名参数别名冲突。
```

(English: cannot specify parameter "Db" because it conflicts with the same-named alias of parameter "Debug".) Not one line of the script body executes.

## Root Cause

PowerShell resolves parameter names by unique prefix, and `[CmdletBinding()]` (or any `[Parameter()]` attribute) injects the common parameters — including `-Debug`, `-Verbose`, `-ErrorAction`, `-Force`, `-Confirm`, `-WhatIf`.

`-Db` is a prefix of `-Debug`, so the binder resolves it to the common parameter first. Once bound, the explicit `-Db` is seen as a second alias for the same slot and the binding is rejected. It is not namespace pollution; it is the interaction between abbreviation resolution and automatically injected common parameters.

## Fix

1. Do not name a parameter after the start of a common parameter: avoid `-Db`, `-Ve`, `-Er`, `-Fo`, `-Co`, `-Wh`, `-De`.
2. Rename to something that cannot abbreviate into one: `-DbPath`, `-DatabasePath`, `-LtmDb`.
3. Passing the value positionally only hides the problem; any caller who uses the named form still fails.

## Verification

`.\script.ps1 -DbPath <path>` runs to completion, and `Get-Help .\script.ps1 -Parameter *` lists no name that is a prefix of a common parameter.
