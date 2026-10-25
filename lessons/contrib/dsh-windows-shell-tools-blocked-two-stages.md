---
domain: "dsh"
title: "DSH shell tools on Windows fail in two stages: the PowerShell script policy, then a sandbox ACL temp grant"
tags:
  - "dsh"
  - "windows"
  - "powershell"
  - "sandbox"
  - "execution-policy"
  - "acl"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3484"
summary_plain: "DSH shell tools on Windows were blocked first by the PowerShell script policy, then by a sandbox ACL grant."
trigger: "sandbox-local windows-acl temp grant materialization failed and its cleanup also failed / prepare-workspace.ps1 UnauthorizedAccess execution policy"
verify: "pwsh and ops_bash return exit 0 and print an echo probe, and a real command (or rea doctor) completes through the restricted sandbox."
provenance:
  issue: "#3484"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH shell tools on Windows fail in two stages: the PowerShell script policy, then a sandbox ACL temp grant

## Problem

On Windows every DSH shell tool (`pwsh`, `ops_bash`) was blocked **before it could start**, and the
block came in two stages.

**Stage 1 — the execution policy.** The prepare-workspace step was a PowerShell script,
`prepare-workspace.ps1`, and it was rejected by the PowerShell execution policy with
`UnauthorizedAccess`. The catch is circular: fixing the policy normally requires a shell, which is
exactly what was unavailable. The policy state was read as:

```
Get-ExecutionPolicy   ->  AllScopes = Undefined
```

**Stage 2 — the sandbox ACL temp grant.** After the policy was changed by hand, outside DSH, the
error became:

```
sandbox-local windows-acl temp grant materialization failed and its cleanup also failed
```

The restricted shell was still unusable. What did work: file read/write tools, and single commands
run with `danger-full-access`.

## Root Cause

Two independent gates sit in series, and fixing the first only exposes the second.

1. **Script execution was off by default.** `AllScopes = Undefined` means the machine policy was
   never configured explicitly, and PowerShell's default then refuses to run scripts. A workspace
   preparation script therefore cannot run, so every shell tool dies before its own logic starts.
   Because the repair is itself a shell command, this stage has to be fixed from outside the tool.
2. **The sandbox could not materialise its temp ACL grant.** The restricted shell works by granting
   the workspace ACLs through a temporary grant; materialising that grant failed, and its cleanup
   failed too. Both failures point at the **grant landing point**, not at the workspace ACLs: the
   workspace itself checked out clean — `icacls` normal, `WRITE_DAC` / `WRITE_OWNER` present, no
   AppContainer package ACE — and the `diagnose-windows-sandbox-acl` skill classified it
   `NOT_THIS_CLASS` with `FIXED=0`, i.e. nothing to repair there. The temp location held no
   `dsh-acl` / `dsh-grant` leftovers, so the failing landing point is outside the workspace
   (`<temp-dir>` or a volume root).

The two stages are easy to merge into one symptom ("shell tools are broken"), which sends the
investigation at the wrong layer: the second failure is not an ACL problem in the workspace.

## Solution

**Step 1 — clear the script-policy gate from outside DSH.** Open a normal PowerShell (not a DSH
shell) and allow locally created scripts for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Re-run a DSH shell tool. If it now starts, stage 1 is cleared; if it fails with the
`sandbox-local windows-acl ...` message, continue to stage 2.

**Step 2 — do not "repair" the workspace ACLs.** Run the `diagnose-windows-sandbox-acl` skill
first. A `NOT_THIS_CLASS` verdict (`WRITE_DAC` / `WRITE_OWNER` present, no AppContainer package ACE,
`FIXED=0`) is a positive result: changing workspace permissions cannot help and adds risk.

**Step 3 — handle the grant landing point.** The two remaining paths are:

- switch the DSH session to full permissions, which bypasses the sandbox's temporary grant
  (a workaround: it removes the sandbox, not the defect); or
- fix the permissions of the location where the temp grant is materialised — suspected to be the
  temp directory or a volume root rather than the workspace.

## Verification

Pass criteria, in order:

1. `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` succeeded and `Get-ExecutionPolicy` no
   longer reports `AllScopes = Undefined` — this alone only proves stage 1.
2. A DSH shell tool returns **exit 0** and prints an echo probe (`pwsh`, then `ops_bash`).
3. A real command (or `rea doctor`) completes **through the restricted sandbox**, not through
   `danger-full-access`.

As reported, only 1–2 were attempted: the restricted `pwsh` / `ops_bash` path kept failing and only
`danger-full-access` executed commands, so stage 2 is **bypassed, not fixed**. The reporter did not
supply the post-fix exit codes or the exact failing path of the grant
(报料者未给出，需复现确认); do not mark the second stage verified on the strength of a working
full-permission command.
