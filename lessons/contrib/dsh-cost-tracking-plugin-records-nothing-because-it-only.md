---
title: "DSH cost-tracking plugin records nothing because it only exposes a service nobody calls"
domain: "dsh"
tags:
  - "dsh"
  - "cost"
  - "plugin"
  - "observability"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3790"
summary_plain: "A cost-tracking plugin is installed and enabled, but its data file (e.g."
trigger: "DSH cost-tracking plugin records nothing because it only exposes a service nobody calls. A cost-tracking plugin is installed and enabled, but its data file…"
verify: "The plugin data directory is created and a ledger/history file grows after a conversation turn."
provenance:
  issue: "#3790"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A cost-tracking plugin is installed and enabled, but its data file (e.g. .cost/ledger.jsonl) is never created and no spend is recorded.

## Root Cause

That plugin only provides a cost service with record/summary methods and registers HTTP routes; it never hooks model calls itself. On this host nothing calls service.record, so every call goes unrecorded.

## Fix

Use a cost plugin that hooks model calls on its own, and check its declared compatibility range against the host version before installing. After restarting, confirm a data directory appears under the DSH home storages folder.

## Verification

The plugin data directory is created and a ledger/history file grows after a conversation turn.
