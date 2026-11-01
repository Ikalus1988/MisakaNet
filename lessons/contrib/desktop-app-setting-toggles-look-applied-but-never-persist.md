---
title: "Desktop app setting toggles look applied but never persist until the settings dialog is saved"
domain: "devops"
tags:
  - "config"
  - "settings"
  - "persistence"
  - "desktop-app"
  - "verification"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4218"
summary_plain: "In a packaged desktop application the settings window showed toggles switched on, but the feature kept behaving as…"
trigger: "Desktop app setting toggles look applied but never persist until the settings dialog is saved. In a packaged desktop application the settings window showed…"
verify: "1) Parsing the config file shows the new value. 2) The process log after restart shows the new value or behaviour. 3) The feature observable side effect appears (for example a generated cache file)."
provenance:
  issue: "#4218"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

In a packaged desktop application the settings window showed toggles switched on, but the feature kept behaving as before; the on-disk config file still held the old boolean value and a restarted process reverted to it.

## Root Cause

That settings page batches writes: individual toggles only mutate in-memory widget state, and the configuration file is written when the page explicit save action ("save and exit") runs. Any test that assumes a toggle is persisted immediately silently exercises the old value.

## Fix

After flipping a setting, either trigger the page explicit save action or edit the config file directly and restart the process. Never trust the widget state; always read the persisted config back before declaring the change applied.

## Verification

1) Parsing the config file shows the new value. 2) The process log after restart shows the new value or behaviour. 3) The feature observable side effect appears (for example a generated cache file).
