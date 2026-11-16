---
title: "A Windows UI Automation observer intended to read settings metadata logged unrel"
domain: "windows"
tags:
  - "windows"
  - "ui"
  - "automation"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4967"
summary_plain: "A Windows UI Automation observer intended to read settings metadata logged unrelated sidebar button labels after a…"
trigger: "A Windows UI Automation observer intended to read settings metadata logged unrel. unrelated sidebar button labels after a normal navigation changed the app…"
verify: "A constrained same-user normal-desktop read of the exact named pane emitted zero unrelated sidebar labels, zero script/secret values, and performed zero UI actions; protected configuration and…"
provenance:
  issue: "#4967"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A Windows UI Automation observer intended to read settings metadata logged unrelated sidebar button labels after a normal navigation changed the app into a conversation/editor surface. No secret field values were accessed.

## Root Cause

The observer continued whole-application button enumeration after the target surface changed, so the same process boundary no longer isolated the intended component.

## Fix

After every navigation, reacquire and assert a unique named component pane. Query only explicitly allowed Name-property labels or explicitly identified nonsecret metadata fields inside that pane. Do not enumerate whole-app button names or read field values while locating the pane. Stop mutations when a configured draft/conversation side-effect boundary is reached. Historical output cannot be erased; disclose it and omit unrelated labels from durable receipts.

## Verification

A constrained same-user normal-desktop read of the exact named pane emitted zero unrelated sidebar labels, zero script/secret values, and performed zero UI actions; protected configuration and authentication hashes matched before/after.

Equivalent constrained read succeeded; zero unrelated labels/secret/script values/UI actions, protected hashes unchanged.
