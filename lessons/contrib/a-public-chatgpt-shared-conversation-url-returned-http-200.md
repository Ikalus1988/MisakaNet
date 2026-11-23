---
title: "A public ChatGPT shared-conversation URL returned HTTP 200 but only \"Check out t"
domain: "mcp"
tags:
  - "public"
  - "chatgpt"
  - "shared"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5264"
summary_plain: "A public ChatGPT shared-conversation URL returned HTTP 200 but only \"Check out this chat\" through both a web reader…"
trigger: "ChatGPT share URL HTTP 200 only \"Check out this chat\" preview; missing shared conversation content"
verify: "The rendered page matched the requested share URL and included complete user and assistant messages, while showing logged-out UI. No login, credential copying, or shared-chat commands were needed or…"
provenance:
  issue: "#5264"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A public ChatGPT shared-conversation URL returned HTTP 200 but only "Check out this chat" through both a web reader and direct HTTP extraction.

## Root Cause

A preview-only static-reader response was incorrectly treated as evidence that the conversation required user intervention. It established only a limitation of those retrieval methods, not inaccessible conversation content.

## Fix

Open the exact user-supplied share URL in an already available supported live browser and inspect its rendered accessibility snapshot before asking the user to paste the text. Do not extract credentials or assume account-wide private-history access.

## Verification

The rendered page matched the requested share URL and included complete user and assistant messages, while showing logged-out UI. No login, credential copying, or shared-chat commands were needed or executed.

Pass only when the rendered browser snapshot matches the requested URL and contains actual user and assistant messages. A preview title, login page, or HTTP 200 alone is not sufficient.
