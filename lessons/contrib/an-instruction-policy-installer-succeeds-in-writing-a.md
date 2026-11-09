---
title: "An instruction-policy installer succeeds in writing a merged file but its immedi"
domain: "mcp"
tags:
  - "an"
  - "instruction"
  - "policy"
status: "published"
evidence_level: "E1"
public_analogue: "a policy-file installer"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4475"
summary_plain: "An instruction-policy installer succeeds in writing a merged file but its immediate validation rejects the…"
trigger: "An instruction-policy installer succeeds in writing a merged file but its immedi. An instruction-policy installer succeeds in writing a merged file but its…"
verify: "Regression cases cover leading LF, CRLF, spaces, tabs, unmanaged prefix/suffix, and repeated installation/validation with byte-exact host notes. All45 unit tests and independent review pass; native…"
provenance:
  issue: "#4475"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

An instruction-policy installer succeeds in writing a merged file but its immediate validation rejects the canonical-policy check when existing host notes begin with blank lines or indentation.

## Root Cause

The initial merge preserved leading host-note whitespace, while the validation/reinstall path removed the managed block and applied strip() to the entire remainder. The merge was not a fixed point: two leading newlines or Markdown indentation disappeared during comparison, even though the managed policy content matched.

## Fix

Replace only the inclusive managed block in place, preserving unmanaged prefix and suffix exactly. Use explicit newline-preserving UTF-8 file IO rather than platform newline translation. Retain separate canonical-policy identity checks; do not discard host instructions just to make whole-file hashes equal.

## Verification

Regression cases cover leading LF, CRLF, spaces, tabs, unmanaged prefix/suffix, and repeated installation/validation with byte-exact host notes. All45 unit tests and independent review pass; native install/check/reinstall/check reports11 trusted hooks and no drift.
