---
title: "A stdio MCP recovery server and CLI/hooks used different SQLite state stores alt"
domain: "mcp"
tags:
  - "stdio"
  - "mcp"
  - "recovery"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4919"
summary_plain: "A stdio MCP recovery server and CLI/hooks used different SQLite state stores although they ran the same source."
trigger: "A stdio MCP recovery server and CLI/hooks used different SQLite state stores alt. although they ran the same source."
verify: "Five isolated regressions passed, including CLI fixture incident visible through MCP under a sanitized environment with no default-home ledger. Native Codex0.169 config/batchWrite preserved complete…"
provenance:
  issue: "#4919"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A stdio MCP recovery server and CLI/hooks used different SQLite state stores although they ran the same source.

## Root Cause

The selected nondefault CODEX_HOME was inherited by local hooks/CLI but absent from the stdio MCP child environment. The runtime defaulted to the account home. Configuration replacement could also erase unrelated MCP options and approvals.

## Fix

Pin env.CODEX_HOME to the explicit installation target using supported per-leaf config updates. Preserve other env entries, disabled state, authentication-related options, timeouts, and approval policies. Never copy or edit ledgers to conceal the mismatch.

## Verification

Five isolated regressions passed, including CLI fixture incident visible through MCP under a sanitized environment with no default-home ledger. Native Codex0.169 config/batchWrite preserved complete persisted TOML except managed leaves. Full scratch install/check found11trusted hooks and retained approval never. Existing live sessions still require separately verified supported refresh or new-session activation.

Scratch native install/check and subprocess state-agreement verified; actual-session deployment explicitly not claimed.
