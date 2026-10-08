---
domain: "devops"
title: "A Windows ACL write sandbox lost command execution: SetNamedSecurityInfoW failed (Win32 5) grantWrite"
tags:
  - "windows"
  - "acl"
  - "sandbox"
  - "icacls"
  - "access-denied"
  - "harness"
status: "draft"
evidence_level: "E0"
created: "2026-10-03"
updated: "2026-10-03"
source: "intake-2301"
summary_plain: "A Windows write sandbox built on file permissions blocked every command until its workspace ACL was rebuilt as admin."
trigger: "every command fails before the process starts / SetNamedSecurityInfoW failed (Win32 5): grantWrite / file tools still work / Windows write sandbox ACL"
verify: "Harness stopped, icacls repair from an elevated shell, harness restarted: a command run through the sandbox writes a file into the system temp dir, outside the workspace."
provenance:
  issue: "#2301"
  source: "dsh (node Misaka14955) lesson_submission"
  evidence: "self-observed"
  note: "Contributor-reported on Windows; not reproduced in this repository. The submitter's workspace path and account name are host-specific and are generalized to <workspace>/<user> below."
---

## Problem

On Windows, an agent harness that implements its write sandbox with NTFS ACLs lost the ability to
execute **any** command. Every shell invocation died before the child process started:

```
SetNamedSecurityInfoW failed (Win32 5): grantWrite(<workspace>)
```

The file read/write tools kept working. That split is the diagnosis, not an inconsistency: the
failure sat in the **sandbox provisioning path** — the descriptor rewrite the sandbox performs
before it will run anything — rather than in the filesystem or in the credentials. Without that
observation the breakage reads as a tool bug, because the tools that *look* broken are the ones
that report no error at all.

## Root Cause

Before running a command the sandbox materializes a security descriptor on the workspace:

1. `GetNamedSecurityInfoW` reads the DACL and the SACL.
2. `SetNamedSecurityInfoW` applies a capability-SID Modify ACE, a Deny ACE for the world SID on
   `FILE_DELETE_CHILD`, and a Low mandatory-integrity label.

The thrown `Win32Error` carries the API name and the code. **Error 5 with only the
`grantWrite(<path>)` context means the access check failed while reading or rewriting the
descriptor** — the message does not say which of the two calls failed, and it does not name a file
that could be at fault. Two Windows rules make that failure reachable:

* reading a **SACL** requires `SeSecurityPrivilege` or ownership of the object;
* writing a **DACL/SACL** requires `WRITE_DAC` / `WRITE_OWNER`.

So a workspace that is *not owned by the interactive user* — or whose explicit ACEs were left in a
state the restricted token cannot rewrite — makes the very step that is supposed to grant access
deny it. The step that enforces the sandbox is the step that breaks the sandbox.

Ruled out by observation, not guesswork: anti-virus, a full disk, ordinary write permission on the
directory, and a non-NTFS volume. Writes performed by the harness itself still succeeded, which is
exactly what localizes the fault to ACL provisioning — the file tools do not go through it.

## Fix

Repair the workspace security descriptor from an **elevated** terminal: the restricted sandbox
process cannot fix the permission that blocks it. In this order, with the harness **stopped first**
so it cannot rewrite the ACL concurrently:

```powershell
# 1. Ownership is the prerequisite for both descriptor writes.
icacls <workspace> /setowner "<user>"

# 2. Restore inheritance and drop stale explicit ACEs left by earlier sandbox runs.
icacls <workspace> /reset

# 3. Replace (not add) the interactive user's ACE with full control including inheritance.
icacls <workspace> /grant:r "<user>:(OI)(CI)F"

# 4. Clear a leftover Low mandatory-integrity label.
icacls <workspace> /setintegritylevel Medium
```

Why each step earns its place:

* `/setowner` — the two rights that are failing are `WRITE_DAC` and `WRITE_OWNER`; taking ownership
  is what grants them.
* `/reset` — earlier sandbox runs leave explicit ACEs behind. Inheriting entries cannot save a
  descriptor that also carries stale explicit entries, so the reset is not optional cleanup.
* `/grant:r` — the `:r` is what makes the repair **idempotent**: it replaces the user's ACE instead
  of appending a duplicate on every run. The repair is safe to re-run end to end.
* `/setintegritylevel Medium` — a Low mandatory-integrity label outlives the ACEs that set it and
  keeps a Medium-integrity process out of the directory even after the ACEs are correct.

Then **restart the harness** and verify (below). Do not run the repair from inside the harness.

**Keep the repair script strictly ASCII.** Windows PowerShell 5.1 mis-decodes non-ASCII in a
BOM-less `.ps1` and then fails with parser errors several lines away from the real problem, so the
repair script itself becomes the next outage. The same mis-decode mechanism is written up in
`lessons/contrib/tts-chinese-encoding-powershell.md` (different symptom); the dedicated lesson on
the PowerShell 5.1 parser-error cascade is not in the corpus yet — source intake `#2300`.

## Verification

After the repair, in the reported case:

* the workspace owner is the interactive user, and the ACL shows that user with `(OI)(CI)(F)`
  alongside inherited Administrators/SYSTEM entries;
* a write/delete self-test **inside** the directory passes;
* a command launched **through the harness sandbox** succeeds, including a write into the system
  temp directory, outside the workspace.

**The outside-the-workspace write is the criterion that matters.** A test confined to the workspace
cannot fail the way this class of bug fails, for two reasons: the workspace is precisely the thing
the repair just changed, so a workspace-local pass is consistent with a descriptor that is still
unusable for command execution; and the file tools that kept working all along do not traverse the
provisioning path, so they will happily confirm a workspace that a shell still cannot use. A write
*outside* the workspace exercises the whole chain — provisioning succeeded, the child process
started, and the write landed in a directory the repair never touched. Treat a workspace-only test
as necessary but not sufficient.

Two residual boundaries, both expected rather than regressions:

* the harness still refuses writes to its own protected data directory even though command execution
  works again — the sandbox grants only the workspace plus a per-session private temp directory, by
  design;
* the repair only took effect after a restart, because it had been done while the harness was
  running.

## Notes

* **Generalization and boundaries.** The submitter's paths and account are environment-specific
  (`C:\Users\<user>\...`); generalized here to `<workspace>` and `<user>`. The account name must be
  resolvable on the host being repaired — a local account, `DOMAIN\user`, or a SID. Repair the
  workspace root the harness actually provisions, not a parent directory: an over-broad `/grant:r`
  with inheritance hands out more than the sandbox ever intended.
* **Symptom triage.** "All commands fail, all file tools work, the error names an API and a bare
  context string" is the signature of provisioning, not of the tool being blamed.
* The submitter filed this as a lesson submission (intake `#2301`, domain label `windows`); `windows`
  is not in `data/domains.json`, so the lesson is filed under `devops` alongside the other Windows
  operations lessons.
