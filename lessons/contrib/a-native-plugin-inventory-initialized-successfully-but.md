---
title: "A native plugin inventory initialized successfully, but small stdout collector l"
domain: "mcp"
tags:
  - "native"
  - "plugin"
  - "inventory"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4968"
summary_plain: "A native plugin inventory initialized successfully, but small stdout collector limits hid its result."
trigger: "A native plugin inventory initialized successfully, but small stdout collector l. limits hid its result."
verify: "The actual response fit a 64 MiB line/128 MiB aggregate bound: 37,346,984-byte maximum line and 37,359,354-byte total stdout. Initialization and complete plugin/list parsed 50 installed entries with…"
provenance:
  issue: "#4968"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A native plugin inventory initialized successfully, but small stdout collector limits hid its result. The installed set was small while the wire response included a much larger available catalog.

## Root Cause

The collector assumed metadata-sized, newline-delimited JSON. The actual plugin/list response was one 37,346,984-byte line. An earlier CLI fresh-cache timeout was a separate observation with unproven cause; it did not establish an authentication or server-startup failure.

## Fix

Use the installed version's supported foreground stdio RPC/schema, strict binary byte-based line and aggregate limits, and measured memory headroom before increasing bounds. Parse the complete bounded response, then persist only installed entries. Retain original timeouts as UNKNOWN; do not replay mutations or attribute network/auth causes without evidence. Drain only the owned child through stdin EOF.

## Verification

The actual response fit a 64 MiB line/128 MiB aggregate bound: 37,346,984-byte maximum line and 37,359,354-byte total stdout. Initialization and complete plugin/list parsed 50 installed entries with no marketplace errors, authentication/configuration hashes unchanged, owned child exit0, and native task completed. This verified the changed inventory method, not the cause or cure of the original CLI timeout.

Complete native response parsed within explicit byte bounds; 50 installed records, no marketplace errors, protected hashes equal, EOF/drain exit0; independent review accepted
