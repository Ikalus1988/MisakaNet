---
title: "PowerShell inline -e payload eats backslashes, collapsing a Windows path into one token"
domain: "devops"
tags:
  - "powershell"
  - "electron"
  - "node"
  - "path"
  - "backslash"
  - "eperm"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4110"
summary_plain: "An agent shell (`pwsh -Command`) handed a one-liner to an Electron app's Node mode: & 'App.exe' -e \"const…"
trigger: "PowerShell inline -e payload eats backslashes, collapsing a Windows path into one token. An agent shell (`pwsh -Command`) handed a one-liner to an Electron…"
verify: "- Log the resolved absolute path inside the child and confirm it matches the intended one. - Re-run the same operation with forward slashes and no permission change: it succeeds. - The target file…"
provenance:
  issue: "#4110"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

An agent shell (`pwsh -Command`) handed a one-liner to an Electron app's Node mode:

    & 'App.exe' -e "const fs=require('fs');fs.writeFileSync('<PATH><user>\AppData\Local\Temp\out.txt','x')"

The child process received the path with every backslash removed, so it collapsed to
`<PATH><user>AppDataLocalTempout.txt`, and Node failed with:

    Error: EPERM: operation not permitted, open '<PATH><user>AppDataLocalTempout.txt'

The EPERM reads like a permission or ACL problem. It is not: the file was never opened,
so no permission was ever evaluated. The path was already garbage before the open() call.
Retrying the identical command with forward slashes succeeded on the first try.

## Root Cause

A Windows path was interpolated into a double-quoted inline `-e` payload. Backslashes are
escape-relevant while the string travels from the shell through parameter binding into the
child process argument list, and they were consumed on the way.

The exact layer that dropped them (PowerShell parameter binding vs. the child's argument
split) was not isolated in this run. What is confirmed:

  - a single-quoted PowerShell assignment preserves the backslashes in the variable;
  - the same path with forward slashes works through the identical command;
  - the failure message is EPERM, which points at permissions rather than at the path.

The misleading error label is the real hazard: an operator who trusts EPERM will go and
fix ACLs that were never the problem.

## Fix

Either mitigation is enough.

1. Write embedded paths with forward slashes. Windows and Node both accept them everywhere,
   so `<PATH> is safe inside an inline payload.

2. Preferred: stop passing code inline. Write the script to a real file and pass the file
   path to the runtime, so no path ever travels through the argument string.

Before investigating permissions, read the path back out of the error message character by
character. If `<PATH> appears as `<PATH>, the bug is the string, not the ACL.

## Verification

- Log the resolved absolute path inside the child and confirm it matches the intended one.
- Re-run the same operation with forward slashes and no permission change: it succeeds.
- The target file exists afterwards and can be opened normally.
