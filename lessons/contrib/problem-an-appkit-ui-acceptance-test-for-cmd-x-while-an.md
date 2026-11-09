---
title: "Problem An AppKit UI acceptance test for \"Cmd-X while an inspector (Get Info) wi"
domain: "development"
tags:
  - "problem"
  - "an"
  - "appkit"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3857"
summary_plain: "An AppKit UI acceptance test for \"Cmd-X while an inspector (Get Info) window is key must not cut files in the…"
trigger: "Problem An AppKit UI acceptance test for \"Cmd-X while an inspector (Get Info) wi. An AppKit UI acceptance test for \"Cmd-X while an inspector (Get Info) window…"
verify: "Mutation check: temporarily replace the guard condition with `false`, rebuild, run the single test -> it must FAIL; restore -> it must PASS. A temporary assertion that dumps selection count, key…"
provenance:
  issue: "#3857"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

An AppKit UI acceptance test for "Cmd-X while an inspector (Get Info) window is key must not cut files in the background window" passed even with the guard code removed, so it proved nothing.

## Root Cause

Two setup gaps: (1) nothing was selected, so the file-cut path had nothing to cut either way; (2) the inspector window opened with an editable NSTextField (Name) as first responder, so the app delegate's cut command took the "editing text -> send cut:" branch and never reached the guarded branch.

## Fix

Select a real fixture file first and wait until the selection is visible in state; after the inspector window becomes key, call keyWindow.makeFirstResponder(nil) so the action reaches the non-text branch. Then send the action via NSApp.sendAction(..., to: nil).

## Verification

Mutation check: temporarily replace the guard condition with `false`, rebuild, run the single test -> it must FAIL; restore -> it must PASS. A temporary assertion that dumps selection count, key window controller and pending-cut count shows which branch ran.
