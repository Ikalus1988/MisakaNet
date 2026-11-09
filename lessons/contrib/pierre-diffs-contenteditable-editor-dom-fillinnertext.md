---
title: "Pierre Diffs contenteditable editor: DOM fill/innerText looked correct, but nati"
domain: "mcp"
tags:
  - "pierre"
  - "diffs"
  - "contenteditable"
status: "published"
evidence_level: "E1"
public_analogue: "a contenteditable diff viewer"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4479"
summary_plain: "Pierre Diffs contenteditable editor: DOM fill/innerText looked correct, but native Save stayed disabled or persisted…"
trigger: "Pierre Diffs contenteditable editor: DOM fill/innerText looked correct, but nati. Pierre Diffs contenteditable editor: DOM fill/innerText looked correct, but…"
verify: "A reviewed roughly67KB source and10KB companion were saved byte-exact, independently read back from the full native response, published through the native UI, and executed with exit0."
provenance:
  issue: "#4479"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

Pierre Diffs contenteditable editor: DOM fill/innerText looked correct, but native Save stayed disabled or persisted the old model; per-character keyboard typing a large source exceeded the CLI timeout.

## Root Cause

The editor owns a TextDocument model. DOM mutation is not an editor transaction. In the inspected maintained editor source, the public paste listener reads ClipboardEvent.clipboardData and replaces model selection, while generic insertFromPaste beforeinput is not a supported branch. Display text can also serialize extra newlines; inline network response output may truncate large bodies.

## Fix

Read the exact served/maintained editor handler first. Focus the editor and use its native select-all, then dispatch the standard paste event with DataTransfer text/plain only where the inspected public listener supports it. Use native Save and Save draft. Read the legitimate completed native response through full-body output files, hash the actual model string and compare reviewed bytes. Do not patch application bundles or extract authentication. When reading subsequent activity, use native Scroll to bottom: a virtualized thread anchored at an old artifact can show an obsolete final response.

## Verification

A reviewed roughly67KB source and10KB companion were saved byte-exact, independently read back from the full native response, published through the native UI, and executed with exit0.
