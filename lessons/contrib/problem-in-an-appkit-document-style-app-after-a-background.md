---
title: "AppKit 文档应用后台任务结束后菜单项灰着：菜单校验时机不对"
domain: "development"
tags:
  - "problem"
  - "in"
  - "an"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4019"
summary_plain: "AppKit 文档应用后台任务结束后菜单项灰着：菜单校验时机不对"
trigger: "AppKit 文档应用后台任务结束后菜单项灰着：菜单校验时机不对"
verify: "Unit tests on the decision function (finished+succeeded -> close, finished+failed -> show, running past the delay -> show without activate). On screen: apply two tags in a row through the menu…"
provenance:
  issue: "#4019"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

In an AppKit document style app, after a background operation (for example tagging a file) finished, menu items that depend on the main window's selection (File > Tags > No Color) became disabled, the next keyboard shortcut did nothing, and an inline rename field would not accept typing.

## Root Cause

The operation's progress window called `NSApp.activate(ignoringOtherApps: true)` and `window.makeKeyAndOrderFront(nil)` in its finish handler and stayed open. It became the key window, so the responder chain no longer reached the main window controller, and `validateMenuItem` saw no selection.

## Fix

For short operations, use a quiet mode: show the progress window only if the operation is still running after a short delay (for example 0.5 s, using a cancellable DispatchWorkItem), and on success close it without activating or making it key. On failure or cancel, still show it and make it key so the error is seen. Put the show/hide/close decision in a pure function so it can be unit-tested.

## Verification

Unit tests on the decision function (finished+succeeded -> close, finished+failed -> show, running past the delay -> show without activate). On screen: apply two tags in a row through the menu; after each, the main window stays key (title bar active), the menu items stay enabled, and no progress window is left open.
