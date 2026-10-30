---
title: "Writes outside the session workspace under workspace-write: escalate once with justification, do not retry through…"
domain: "devops"
tags:
  - "sandbox"
  - "workspace-write"
  - "escalation"
  - "file-access"
  - "acl"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-2867"
summary_plain: "Profile edits under $DSH_HOME (outside the session workspace) were denied with 'sandbox: file access denied' under the…"
trigger: "Writes outside the session workspace under workspace-write: escalate once with justification, do not retry through…. Profile edits under $DSH_HOME (outside…"
verify: "The operation completes under the escalated run; a backup of the prior content exists; operations inside the workspace continue to work without escalation."
provenance:
  issue: "#2867"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Profile edits under $DSH_HOME (outside the session workspace) were denied with 'sandbox: file access denied' under the workspace-write policy. Time was lost trying equivalent operations through PowerShell, Node fs and the host CLI before escalating - all of which hit the same policy.

## Root Cause

Treating a policy denial as a tooling problem. A confinement-mode denial is a boundary enforced below the API surface, so switching API cannot succeed.

## Fix

On the first 'sandbox: file access denied', stop trying alternate APIs and request one-shot escalation for that exact operation with a stated justification. Back up the file first; verify the resolved absolute path is the intended target.

## Verification

The operation completes under the escalated run; a backup of the prior content exists; operations inside the workspace continue to work without escalation.
