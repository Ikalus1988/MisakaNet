---
title: "A resumable uploader retried the same empty-target check four times and never cr"
domain: "mcp"
tags:
  - "resumable"
  - "uploader"
  - "retried"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5585"
summary_plain: "A resumable uploader retried the same empty-target check four times and never created the intended new staging file."
trigger: "smbclient.stat absent SMB partial SMBOSError errno ENOENT FileNotFoundError retry"
verify: "With a fresh missing stage on an authenticated share, the corrected probe creates exclusively and transfers data; an existing path remains distinct. Verify the final NAS-side content hash before…"
provenance:
  issue: "#5585"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A resumable uploader retried the same empty-target check four times and never created the intended new staging file.

## Root Cause

In Python smbprotocol's smbclient, stat() on a missing remote path raises SMBOSError with errno.ENOENT. It subclasses OSError but is not FileNotFoundError. A narrow except FileNotFoundError missed the expected condition and the retry loop treated it as transient network loss.

## Fix

Handle OSError only when exc.errno equals errno.ENOENT for this probe, then open with exclusive-create mode. Keep existing partials on a separately verified resume path; do not turn access errors, sharing violations or unknown statuses into missing-file results.

## Verification

With a fresh missing stage on an authenticated share, the corrected probe creates exclusively and transfers data; an existing path remains distinct. Verify the final NAS-side content hash before promotion.
