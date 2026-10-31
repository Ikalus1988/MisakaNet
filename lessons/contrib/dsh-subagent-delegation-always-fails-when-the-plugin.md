---
title: "DSH subagent delegation always fails when the plugin hardcodes a provider that does not exist"
domain: "dsh"
tags:
  - "dsh"
  - "subagent"
  - "provider"
  - "plugin"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3787"
summary_plain: "A plugin that starts a subagent returns \"subagent did not finish (error)\" every time, with no useful diagnostic."
trigger: "DSH subagent delegation always fails when the plugin hardcodes a provider that does not exist. A plugin that starts a subagent returns \"subagent did not…"
verify: "The delegation returns ok:true with a real report, and the same call fails again if the provider is set back to the unknown name."
provenance:
  issue: "#3787"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A plugin that starts a subagent returns "subagent did not finish (error)" every time, with no useful diagnostic.

## Root Cause

The plugin passed agentOptions.provider = "apii" (a provider name from the author machine). The host has no such provider, so activation fails before the subagent runs.

## Fix

Replace the provider with one the host actually exposes (list them from the host model catalogue) and set a model name that exists there. Also check the fallback in code: cfg.provider || "apii" keeps failing even after clearing the setting.

## Verification

The delegation returns ok:true with a real report, and the same call fails again if the provider is set back to the unknown name.
