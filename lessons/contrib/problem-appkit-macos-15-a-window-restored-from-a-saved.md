---
title: "AppKit 保存的窗口恢复后矮了 28pt：styleMask 在 setFrame 之后才插 fullSizeContentView"
domain: "development"
tags:
  - "problem"
  - "appkit"
  - "macos"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3848"
summary_plain: "AppKit (macOS 15+): a window restored from a saved frame came back about 28 pt shorter than saved (900x650 requested…"
trigger: "Problem AppKit (macOS 15+): a window restored from a saved frame came back about. AppKit (macOS 15+): a window restored from a saved frame came back about 28…"
verify: "Instrumented test: build the window controller with a saved frame (origin inside `NSScreen.main.visibleFrame`, so a visible Dock does not shift it) and assert that the window frame size and origin…"
provenance:
  issue: "#3848"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

AppKit (macOS 15+): a window restored from a saved frame came back about 28 pt shorter than saved (900x650 requested -> 900x622). Restored windows also shrank further to minSize when a content view controller was attached.

## Root Cause

1. The window was created without `.fullSizeContentView`, then `window.setFrame(saved)` ran, then `window.styleMask.insert(.fullSizeContentView)`. A style-mask change keeps the CONTENT size constant, so adding full-size content makes the content rect equal the frame, and the frame shrinks by the title-bar height.
2. `window.contentViewController = vc` resizes the window to `vc.view.frame`; a container whose `loadView` uses `NSView(frame: .zero)` collapses the window to its minSize.

## Fix

- Put `.fullSizeContentView` in the initial `styleMask:` of the window initializer instead of inserting it later.
- Attach content with a helper that keeps the size: `let size = contentRect(forFrameRect: frame).size; contentViewController = vc; if contentView?.frame.size != size { setContentSize(size) }`.
- Call `window.center()` only when there is no saved frame, or restored windows lose their position.

## Verification

Instrumented test: build the window controller with a saved frame (origin inside `NSScreen.main.visibleFrame`, so a visible Dock does not shift it) and assert that the window frame size and origin equal the saved values. It failed before the fix (900x622) and passes after. Screen check: Quit and Keep Windows, relaunch, and the window comes back at the same size and position.
