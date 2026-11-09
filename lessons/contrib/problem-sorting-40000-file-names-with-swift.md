---
title: "Swift localizedStandardCompare 排序 4 万文件名慢到 200ms：桥接 NSString + 跨核合并得不偿失"
domain: "mcp"
tags:
  - "problem"
  - "sorting"
  - "file"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3861"
summary_plain: "Sorting ~40,000 file names with Swift `String.localizedStandardCompare` (Finder-style order) took about 200 ms in a…"
trigger: "Problem Sorting ~40,000 file names with Swift `String.localizedStandardCompare`. Sorting ~40,000 file names with Swift `String.localizedStandardCompare`…"
verify: "Standalone `swiftc -O` benchmark, 40,000 names: short names 195 → 108 ms; long Unicode names 270 → 180 ms; the order was identical in each run. In the app, first rows of a 40,000-file folder went…"
provenance:
  issue: "#3861"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

Sorting ~40,000 file names with Swift `String.localizedStandardCompare` (Finder-style order) took about 200 ms in a release build. Splitting the sort across all cores (`DispatchQueue.concurrentPerform` with a chunked sort and a pairwise merge) made it 80–180 ms SLOWER in every A/B run.

## Root Cause

A CPU sample (`sample <pid> 3 1`) showed what each comparison costs. (1) `StringProtocol.localizedStandardCompare` bridges BOTH Swift strings to NSString on every call, and names of 15 bytes or less (small strings) allocate new storage each time. (2) `-[NSString localizedStandardCompare:]` reads the current locale through `LocaleCache.currentNSLocale`, behind an `os_unfair_lock`, and returns an autoreleased object. More threads only wait on the same lock.

## Fix

Bridge each key once (`let keys = items.map { $0.name as NSString }`), sort an `Int` index array with `keys[i].localizedStandardCompare(keys[j] as String)` and the same tie-break, then map the indices back to the items. It is the same comparison method, so the order is identical. Moving Ints instead of large structs also helps. Do not parallelize localized string comparison.

## Verification

Standalone `swiftc -O` benchmark, 40,000 names: short names 195 → 108 ms; long Unicode names 270 → 180 ms; the order was identical in each run. In the app, first rows of a 40,000-file folder went from 0.56 s to 0.42–0.46 s. A unit test compares the keyed sort against the per-comparison comparator on 3,000 shuffled names (mixed case, Unicode, numbers), in both directions.
