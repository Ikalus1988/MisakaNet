---
title: "Suggested lesson title: \"The preset switch was on the user's first screenshot: r"
domain: "dsh"
tags:
  - "configforms.developertools.enabled"
  - "developertools"
  - "suggested"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-4211"
summary_plain: "Suggested lesson title: \"The preset switch was on the user's first screenshot: read the settings UI before grepping…"
trigger: "Suggested lesson title: \"The preset switch was on the user's first screenshot: r. read the settings UI before grepping the bundle\"."
verify: "Toggle on -> new session picker lists four presets immediately; toggle off -> two (standard, cordis); no restart either way. Same machine: plugin-page \"Developer Tools\" toggle does not change the…"
provenance:
  issue: "#4211"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Suggested lesson title: "The preset switch was on the user's first screenshot: read the settings UI before grepping the bundle". User asked why only two agent presets appeared in a DSH new session. The agent answered with a config field, then a plugin-page toggle, then edited the profile patch to developerTools: true — three answers, three restarts, still two presets. The real switch had been visible in the user's very first screenshot: Settings -> General -> "显示代码工作视图 / Show coding view", whose own description says it enables selecting the full agent preset set. Turning it on listed all four presets (standard / PTC / minimal / cordis) immediately, no restart.

## Root Cause

the agent searched the implementation (bundle strings, config keys, client source) instead of reading the settings page the user had already shown; bundle archaeology yielded a plausible but wrong causal chain and it never cross-checked the UI description of the toggle that writes configForms.developerTools.enabled. A shipped settings UI is authoritative for "where is this switch"; internal keys are not.

## Fix

Walk the settings UI top to bottom and match the user's promise-shaped description text, not internal config keys. Concrete map from this incident: preset gating = Settings -> General -> "Show coding view" (developerTools.title), described in-product as enabling full agent-preset switching; it is `configForms.developerTools.enabled` (Schema.boolean default false), subscribed by the client, so it applies live with no restart. The plugin page's experimental "Developer Tools" toggle enables the inspector bundle (unredacted capture, NodeJS debug) and does NOT unlock presets. The `developerTools` field under ui-settings-account in cordis.patch.yml is not the effective store.

## Verification

Toggle on -> new session picker lists four presets immediately; toggle off -> two (standard, cordis); no restart either way. Same machine: plugin-page "Developer Tools" toggle does not change the preset list, and editing developerTools under ui-settings-account in cordis.patch.yml does not either.
