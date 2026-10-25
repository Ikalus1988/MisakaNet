---
title: "NSAccessibilityElement children report as disabled until accessibilityEnabled is set explicitly"
domain: "development"
tags:
  - "macos"
  - "appkit"
  - "accessibility"
  - "nsaccessibilityelement"
  - "ax-tree"
  - "disabled"
  - "automation"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "自定义控件的辅助功能子元素要显式设 accessibilityEnabled，否则辅助功能树把它们报成 disabled。"
trigger: "button (disabled) NSAccessibilityElement isAccessibilityEnabled"
verify: "装好的 app 里用 AX 树查子元素不再带 disabled，激活后真实操作完成"
source: "intake-3616"
provenance:
  issue: "#3616"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# NSAccessibilityElement children report as disabled until accessibilityEnabled is set explicitly

## Problem

A custom macOS AppKit control exposed `NSAccessibilityElement` children with button roles and press
callbacks. The live accessibility tree reported those buttons as **disabled**, so assistive technology
and AX-driven automation saw pressable-looking buttons they refused to press.

The observed tree line is short and easy to miss:

```
button (disabled)
```

The reporter had already searched the public lesson index for
`NSAccessibilityElement isAccessibilityEnabled button disabled` and had found no matching lesson.

## Root Cause

`accessibilityEnabled` is not inherited from the owning control and does not default to the control's
interaction mode. A child element created as a plain `NSAccessibilityElement` with
`accessibilityRole = .button` plus a press handler ends up with role and action correct but the
enabled flag at its default — so the element advertises a button that cannot be activated as far as
the client is concerned.

The behaviour is therefore split across two places that can disagree: the control knows whether it is
interactive right now (mode-dependent), while each child element carries its own enabled state that
someone has to write. Nothing writes it, so the tree is wrong regardless of what the control does on
click.

## Solution

### Step 1 — Set `accessibilityEnabled` when building each child

Derive the flag from the control's interaction mode at construction time, for every child, not just
the first:

```swift
let child = NSAccessibilityElement()
child.accessibilityRole = .button
child.accessibilityLabel = label
child.accessibilityEnabled = isInteractive   // explicit: defaults do not follow the control
child.setAccessibilityParent(self)
```

### Step 2 — Guard the action itself

Keeping the flag honest only matters if the action also refuses to run when disabled — otherwise a
client that presses anyway still triggers the callback:

```swift
override func accessibilityPerformPress() -> Bool {
    guard isAccessibilityEnabled else { return false }
    performAction()
    return true
}
```

### Step 3 — Rebuild the children when the mode changes

If the control can switch between interactive and non-interactive modes while visible, the children's
enabled flags must be updated (or the children rebuilt) on that transition; the AX tree is read
asynchronously and will not pick up a mode change on its own.

## Verification

Two layers, both from the reporter's plan:

1. **Regression test, both modes.** Interactive mode: assert `accessibilityEnabled` is true for every
   child and that a press dispatches the callback. Non-interactive mode: assert the flag is false and
   that a press is rejected (returns false, callback not called).
2. **Live tree.** Inspect the **installed** app's native accessibility tree, confirm the child no
   longer reports `(disabled)`, then activate an enabled child and confirm the real operation
   completes.

Layer 2 is required: a unit test can assert the property you set, but only the installed app shows
what the tree actually advertises.

## Notes

- A control can also be disabled by an ancestor, so if a child is still reported disabled after this
  fix, walk the parent chain before re-editing the child.
- The intake listed no console output beyond `button (disabled)`; the reporter's exact AppKit version
  and accessibility-tree dump were not provided and need reproduction to confirm on another machine.
