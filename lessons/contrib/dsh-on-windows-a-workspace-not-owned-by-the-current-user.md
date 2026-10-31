---
title: "DSH on Windows: a workspace not owned by the current user blocks every shell tool (WRITE_OWNER), while ops_bash with…"
domain: "devops"
tags:
  - "dsh"
  - "windows"
  - "sandbox"
  - "workspace-owner"
  - "write-owner"
  - "acl"
  - "shell-blocked"
  - "takeown"
  - "danger-full-access"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3899"
summary_plain: "On Windows, DeepSeek Harness refused to start ANY shell tool for a workspace directory, before the command itself ran…"
trigger: "DSH on Windows: a workspace not owned by the current user blocks every shell tool (WRITE_OWNER), while ops_bash with…. On Windows, DeepSeek Harness refused to…"
verify: "After fixing ownership, a plain `echo ok` through `ops_bash` (no special permission) returns output instead of the preparation error. Ownership is visible with `dir /q <dir>` (owner column shows the…"
provenance:
  issue: "#3899"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

On Windows, DeepSeek Harness refused to start ANY shell tool for a workspace directory, before the command itself ran:

```
DSH workspace preparation failed: the workspace root <PATH><workspace> does not meet the sandbox
prerequisite (the host needs WRITE_OWNER on it): Workspace is not owned by the current user;
refusing automatic ACL preparation. Fix the folder's owner or permissions, open a workspace you own,
or use danger-full-access. This is a folder permission problem, not a DSH [REDACTED:bearer_token]
[COMMAND_FAILED; effects: none; retry: never]
```

Both `ops_bash` and `pwsh` died identically. Raising `sandbox_permissions` on `pwsh` did not help, which makes it look like an [REDACTED:bearer_token] - but the error explicitly says it is NOT one. The workspace root's owner was a different account than the running user, so the folder gave the current user no `WRITE_OWNER` even though ordinary reads and writes inside it worked fine.

## Root Cause

DSH prepares a workspace before running any shell command: it needs `WRITE_OWNER` on the workspace root in order to materialise its temporary ACL grant, and it refuses to "automatically prepare ACLs" on a directory it does not own. That check runs before the command, so the failure is identical for every shell tool, and no command-level retry or per-call permission escalation on the individual tool can pass it.

This is a distinct failure from the other known Windows shell blockers (PowerShell execution policy, then the sandbox ACL temp grant failing to materialise): here the workspace ACLs may be perfectly fine for the current user, but *ownership* is not, and the gate fires earlier.

The asymmetry is the operationally important part: `ops_bash` with `sandbox_permissions: danger-full-access` bypasses workspace preparation and does execute, while `pwsh` with the same flag still fails with the same `WRITE_OWNER` error. So the presence of danger-full-access does not imply every shell tool is usable.

## Fix

Own the workspace, or run the command from a mode that does not prepare the workspace.

1. Take ownership from an elevated shell outside DSH: `takeown /f <dir> /r /d y` then `icacls <dir> /grant %USERNAME%:(OI)(CI)F`. Or simply point DSH at a directory the current user already owns - the fastest fix.
2. Until then, use the asymmetry: `ops_bash` invoked with `danger-full-access` does run, `pwsh` with the same permission does not. Reach for `ops_bash` + `danger-full-access` rather than `pwsh`.
3. File read/write tools keep working throughout, so you can still script around the block - including writing a `.bat` into the workspace and launching it through `ops_bash` + `danger-full-access` (also a way around Git-Bash mangling `cmd.exe /c` argument quoting: the single-quoted form silently does nothing and still exits 0).

## Verification

After fixing ownership, a plain `echo ok` through `ops_bash` (no special permission) returns output instead of the preparation error. Ownership is visible with `dir /q <dir>` (owner column shows the current user) or `Get-Acl <dir>`. Negative check: while blocked, `pwsh` even with danger-full-access still fails - do not conclude from one `pwsh` failure that no shell on the machine can run.
