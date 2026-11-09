---
title: "A cross-platform recovery CLI emitted a POSIX-quoted executable and JSON argumen"
domain: "windows"
tags:
  - "cross"
  - "platform"
  - "recovery"
status: "published"
evidence_level: "E1"
public_analogue: "POSIX shell quoting"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4469"
summary_plain: "A cross-platform recovery CLI emitted a POSIX-quoted executable and JSON argument."
trigger: "A cross-platform recovery CLI emitted a POSIX-quoted executable and JSON argumen. A cross-platform recovery CLI emitted a POSIX-quoted executable and JSON…"
verify: "The emitted benign status command executed unchanged under actual Windows PowerShell 5.1, exited zero, and returned the expected actor. Tests rejected shell payloads, malformed Base64 and altered…"
provenance:
  issue: "#4469"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A cross-platform recovery CLI emitted a POSIX-quoted executable and JSON argument. On Windows PowerShell 5.1 the exact generated command failed with ParserError UnexpectedToken instead of returning JSON.

## Root Cause

POSIX shlex quoting is not PowerShell invocation syntax; a quoted executable needs the call operator. Native JSON argv handling also differs across PowerShell versions.

## Fix

Use a platform-specific command renderer bound to the exact interpreter/script. On Windows emit the call operator with literal-quoted paths and transport the JSON as a validated URL-safe Base64 ASCII argument. Decode and validate JSON in the CLI. Restrict the recovery exemption to that exact grammar; reject extra operators/substitution. Keep POSIX rendering separate.

## Verification

The emitted benign status command executed unchanged under actual Windows PowerShell 5.1, exited zero, and returned the expected actor. Tests rejected shell payloads, malformed Base64 and altered executable/script bindings.
