---
title: "NSOutlineView 刷新子目录后选中态丢失：reloadItem 重建了行"
domain: "development"
tags:
  - "problem"
  - "appkit"
  - "nsoutlineview"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4023"
summary_plain: "NSOutlineView 刷新子目录后选中态丢失：reloadItem 重建了行"
trigger: "NSOutlineView 刷新子目录后选中态丢失：reloadItem 重建了行"
verify: "An app-level acceptance case selects a file inside an expanded subfolder, applies a change through the real menu item, waits for the subfolder refresh, and asserts that the selection still equals…"
provenance:
  issue: "#4023"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

AppKit NSOutlineView (view-based, list of files with folders that expand). After a file change inside an expanded subfolder, the app reloads that folder's children with `reloadItem(parent, reloadChildren: true)` and then calls its own restoreSelection(). The selected child row is still lost, so the next menu command acting on "the selection" does nothing (beeps on empty selection).

## Root Cause

`reloadItem(_:reloadChildren:)` removes the child rows for a moment, which fires `outlineViewSelectionDidChange` synchronously. The delegate copies the table's (now empty) selection into the model's selectedURLs before restoreSelection runs, so restore has nothing to put back. It is only visible when reloads of expanded children happen after every change, not only on first expand.

## Fix

Put the model-sync guard (the same flag that restoreSelection uses to ignore its own selection events) around the reloadItem call:
```swift
isRestoringSelection = true
table.reloadItem(parent, reloadChildren: true)
isRestoringSelection = false
restoreSelection()
```
Do not re-derive the selection from the table afterwards: that drops selected items whose rows are still loading.

## Verification

An app-level acceptance case selects a file inside an expanded subfolder, applies a change through the real menu item, waits for the subfolder refresh, and asserts that the selection still equals [file]. Then it applies a second command, which must land. Without the guard, the case fails with "selection after first command: []". With the guard, it passes.
