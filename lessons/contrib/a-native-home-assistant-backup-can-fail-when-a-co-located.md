---
title: "A native Home Assistant backup can fail when a co-located application creates an"
domain: "mcp"
tags:
  - "native"
  - "home"
  - "assistant"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5588"
summary_plain: "A native Home Assistant backup can fail when a co-located application creates and removes SQLite WAL sidecars under…"
trigger: "Error adding .sqlite-shm to tarfile: [Errno 2] No such file or directory (FileNotFoundError)"
verify: "Test separate writer commits and truncating checkpoints with the guard idle; verify full native backup completes, required components decrypt/read back, guards release and app state returns."
provenance:
  issue: "#5588"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A native Home Assistant backup can fail when a co-located application creates and removes SQLite WAL sidecars under the configuration tree.

## Root Cause

The backup enumerates directory entries, then opens them. SQLite can remove a transient .sqlite-shm file after the last connection closes, making an earlier listing stale. A generic failure writing to a network mount is not proof of this race; check the actual job error.

## Fix

On a disposable WAL database first verify that an idle read-only autocommit connection retains the SHM inode after a writer closes, while independent writers can commit and checkpoint normally. For a live rehearsal, open verified handles within the DB owner's container, finish the short reads (do not hold a transaction), monitor inode continuity and WAL sizes, and close after the native backup finishes. Preserve active databases with proper SQLite snapshots separately. Do not delete WAL files. If other file churn remains, arrange a coordinated maintenance window instead.

## Verification

Test separate writer commits and truncating checkpoints with the guard idle; verify full native backup completes, required components decrypt/read back, guards release and app state returns.
