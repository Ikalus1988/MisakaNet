---
title: "窗口以 0 高度打开（不可见）：设置 contentViewController 时容器根视图还是 .zero"
domain: "development"
tags:
  - "problem"
  - "appkit"
  - "window"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3843"
summary_plain: "AppKit window opened with zero height (invisible) after its content was moved into a container NSViewController."
trigger: "Problem AppKit window opened with zero height (invisible) after its content was. AppKit window opened with zero height (invisible) after its content was moved…"
verify: "List the app's windows (e.g. accessibility or CGWindowList bounds) after opening the window: height must be > 0 and equal to the intended size; a screenshot shows the window."
provenance:
  issue: "#3843"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

AppKit window opened with zero height (invisible) after its content was moved into a container NSViewController. Unit tests and code review did not catch it; only a screen check did.

## Root Cause

Setting `window.contentViewController = vc` resizes the window to `vc.view.frame`. The container's `loadView` created its root view with `frame: .zero` and pinned the real content (an NSScrollView, no intrinsic height) with Auto Layout, so the window collapsed to height 0. Before the change the code used `window.contentView = view`, which keeps the window's contentRect size.

## Fix

After assigning contentViewController, call `window.setContentSize(NSSize(width: W, height: H))` (or give the container's root view a non-zero initial frame / preferredContentSize).

## Verification

List the app's windows (e.g. accessibility or CGWindowList bounds) after opening the window: height must be > 0 and equal to the intended size; a screenshot shows the window.
