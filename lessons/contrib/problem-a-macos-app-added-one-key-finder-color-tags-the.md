---
title: "Problem A macOS app added one-key Finder color tags. The menu listed \"No Color,"
domain: "development"
tags:
  - "problem"
  - "macos"
  - "app"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4018"
summary_plain: "A macOS app added one-key Finder color tags."
trigger: "Problem A macOS app added one-key Finder color tags. The menu listed \"No Color,. A macOS app added one-key Finder color tags."
verify: "Print the real order: `printf 'import AppKit\\nprint(NSWorkspace.shared.fileLabels)\\n' > fl.swift && swift fl.swift`. Then tag a file with the Red key and check that `mdls -name kMDItemUserTags file`…"
provenance:
  issue: "#4018"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

A macOS app added one-key Finder color tags. The menu listed "No Color, Red, Orange, Yellow, Green, Blue, Purple, Gray" on Control-0…7 and passed the key number as the Finder palette index. Control-1 "Red" applied Gray, Control-2 "Orange" applied Green, and so on. Unit tests passed, because the test fixture also wrote a "Red" tag with index 1.

## Root Cause

Finder's palette index (used in `com.apple.metadata:_kMDItemUserTags` entries as "Name\nIndex", and the index into `NSWorkspace.shared.fileLabels`) does not follow the visible menu order. `fileLabels` is ["None","Gray","Green","Purple","Blue","Yellow","Red","Orange"]: Red is 6, Orange 7, Yellow 5, Green 2, Blue 4, Purple 3, Gray 1. The fixture was written from the same wrong assumption, so the test and the code agreed with each other and were both wrong.

## Fix

Map menu order to palette index explicitly, for example `[0, 6, 7, 5, 2, 4, 3, 1]` for None, Red, Orange, Yellow, Green, Blue, Purple, Gray. Write fixtures with the real indexes ("Red\n6").

## Verification

Print the real order: `printf 'import AppKit\nprint(NSWorkspace.shared.fileLabels)\n' > fl.swift && swift fl.swift`. Then tag a file with the Red key and check that `mdls -name kMDItemUserTags file` shows Red and Finder shows a red dot.
