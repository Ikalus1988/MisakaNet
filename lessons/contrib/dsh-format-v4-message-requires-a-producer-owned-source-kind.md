---
title: "DSH: 'format v4 message requires a producer-owned source kind' rejects plugin messages that keep the retired…"
domain: "dsh"
tags:
  - "dsh"
  - "session-format"
  - "plugin"
  - "source-kind"
  - "message-injection"
  - "error-triage"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3140"
summary_plain: "On DSH (DeepSeek Harness) 0.2.0-rc.2, a third-party plugin that injects a message during a turn started failing every…"
trigger: "DSH: 'format v4 message requires a producer-owned source kind' rejects plugin messages that keep the retired…. On DSH (DeepSeek Harness) 0.2.0-rc.2, a…"
verify: "1) node --check on the patched file exits 0. 2) grep the plugin tree for kind:\\s*[\"']plugin[\"'] - production code should have zero hits (runtime migration fixtures and doc comments excepted). 3)…"
public_analogue: "a schema version field"
provenance:
  issue: "#3140"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

On DSH (DeepSeek Harness) 0.2.0-rc.2, a third-party plugin that injects a message during a turn started failing every turn with://[REDACTED:url_credential]@host 0.1.1 recall - its agent pre-step hook splices a synthetic user message into decision.messages. The plugin stays installed and mounted; only the injection (and the visible turn) breaks. The same string is also raised while reading a session whose stored rows still carry the pre-v4 wrapper.

## Root Cause

Session format v4 retired the bare plugin source wrapper {kind://[REDACTED:url_credential]@host or, for role system, system-prompt) and RELEASED_SAME_NAME_PRODUCERS (user-approval, tool-jobs, dsh-session-title-llm, goal, ...), but NEW writes are never rewritten. A plugin ported from the v3 era keeps createUserMessage({source:{kind:"plugin",plugin:"memos-cloud",form:"recall"}}) and therefore has every injection refused. The refusal leaves no row, so the session archive looks clean and the only symptom is the error text.

## Fix

Stamp a producer-owned kind on every message a plugin creates: source {kind: "plugin:<plugin-id>"}. This is exactly the shape DSH's own v3->v4 migration derives for those old rows and the shape shipped plugins use (plugin:dsh-better-sidebar, plugin:hindsight). For memos-cloud-dsh-plugin 0.1.1 patch lib/index.js createRecallMessage(): replace 'kind: "plugin", plugin: "memos-cloud"' with 'kind: "plugin:memos-cloud", plugin: "memos-cloud"' (the legacy plugin field may stay; the validator only inspects kind). Never emit the pre-v4 wrapper on new writes.

## Verification

1) node --check on the patched file exits 0. 2) grep the plugin tree for kind:\s*["']plugin["'] - production code should have zero hits (runtime migration fixtures and doc comments excepted). 3) Restart DSH so the module is re-read. 4) Run a turn: no SessionFormatError. 5) Confirm the injected row now persists with source.kind = plugin:<id> by decompressing the session archive ~/.dsh/sessions/<workspace-key>/<session-id>/session.v4.jsonl.zstd (multi-frame zstd: split on the 28 B5 2F FD magic and zlib.zstdDecompressSync each frame).
