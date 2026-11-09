---
title: "A reviewed Python source bundle had identical file bytes on Windows and POSIX bu"
domain: "windows"
tags:
  - "reviewed"
  - "python"
  - "source"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4470"
summary_plain: "A reviewed Python source bundle had identical file bytes on Windows and POSIX but failed its aggregate SHA256 manifest…"
trigger: "A reviewed Python source bundle had identical file bytes on Windows and POSIX bu. A reviewed Python source bundle had identical file bytes on Windows and…"
verify: "A regression using Windows path objects produced the same key set as POSIX. The rebuilt archive's manifest matched on actual Windows, Linux x86_64, and Linux aarch64 hosts before installation…"
provenance:
  issue: "#4470"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A reviewed Python source bundle had identical file bytes on Windows and POSIX but failed its aggregate SHA256 manifest check after transfer.

## Root Cause

Manifest keys used str(path.relative_to(root)), which renders backslashes on Windows and forward slashes on POSIX. Hashing sorted JSON then produced different aggregate fingerprints for the same archive.

## Fix

Normalize manifest keys with path.relative_to(root).as_posix(), while hashing source file bytes unchanged. Rebuild the reviewed bundle and refresh dependent fingerprints; do not waive integrity assertions to get past the mismatch.

## Verification

A regression using Windows path objects produced the same key set as POSIX. The rebuilt archive's manifest matched on actual Windows, Linux x86_64, and Linux aarch64 hosts before installation; subsequent native configuration and functional checks passed.
