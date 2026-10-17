---
title: "A parked license-gate screen is not tamper detection: walk the UI tree first"
domain: "automation"
tags:
  - "desktop-automation"
  - "uiautomation"
  - "windows"
  - "flutter-desktop"
  - "license-gate"
  - "misdiagnosis"
  - "accessibility-tree"
  - "reverse-engineering"
status: "published"
created: "2026-10-17"
updated: "2026-10-17"
source: "intake #3453 — desktop app 'stuck' at a license-gate screen misdiagnosed as tamper detection"
evidence_level: "E0"
summary_plain: "桌面应用卡住不一定被反篡改拦住，可能只是停在等输入框的页面上；先把整屏控件读全，再怀疑授权层。"
trigger: "desktop app stuck refuses to continue suspected license tamper detection Flutter Windows UIA EditControl ButtonControl click does not advance"
verify: "UIA tree dump lists the on-screen EditControl and its confirm ButtonControl; filling the field and calling Click() advances the app to the next window"
provenance:
  issue: "#3453"
  source: "MCP intake (dsh), contributor-reported"
---

## Problem

A packaged Windows desktop app (a Flutter shell) appeared to stop at one page and
refuse to continue, no matter how it was driven. Automation attempts did nothing:
raw coordinate clicks landed on the right pixels and the screen did not change, so the
app looked like it was actively defending itself.

Because the app was license-bearing and closed-source, five investigation rounds went
deeper and deeper on the *theory* that it had detected tampering. Each round was
internally plausible and all of them were wrong:

- system proxy / intercepting certs were re-checked and re-configured,
- the app's encrypted ticket file was located and its hashes reasoned about,
- server-side device binding was suspected and probed,
- PE integrity / self-hash manifests were searched for,
- anti-debug string tables were dumped and scanned.

None of it moved the app one screen. The expensive mistake was **attributing a static,
undriveable screen to a deep adversarial cause before reading the whole screen.**

## Root Cause

The window was not blocked by tamper detection. It was parked on a normal
license-gate page waiting for human input:

- an input field labelled `请输入安全码` ("please enter the safety code"), and
- a full-width confirm button labelled `验证登录` ("verify login").

Two factors made this invisible to the previous attempts:

1. **Raw synthetic input does not reach Flutter Windows widgets.** Coordinates and
   low-level mouse events were delivered to the process but did not activate the
   controls, which reinforced the "it is blocking me on purpose" story.
2. **Nobody enumerated the controls.** Every theory was tested against the process and
   its files; the on-screen widget tree was never read. The screen was assumed to be an
   inert "you are blocked" panel rather than a form.

The app was reachable the whole time. The UI Automation (UIA) tree for that same stuck
screen listed 10 nodes, including the `EditControl` for the safety code and the
`ButtonControl` for `验证登录`.

## Solution

Replace theory-first debugging with a fixed screen-reading pass. Only escalate to
proxy / licensing / server / integrity causes **after** every control on the visible
screen has been enumerated and driven.

### Step 1 — Dump the full UI Automation tree of the stuck window

Do not click. First list every control and its bounding rectangle.

```python
from uiautomation import WindowControl

win = WindowControl(Name="<app window title>")
win.Exists(maxSearchSeconds=5)
win.SetTopmost()

def dump(ctrl, depth=0):
    print("  " * depth + f"{ctrl.ControlTypeName} name={ctrl.Name!r} rect={ctrl.BoundingRectangle}")
    for child in ctrl.GetChildren():
        dump(child, depth + 1)

dump(win)
```

If the tree is nearly empty, the app's accessibility layer may be off; a screen reader
or `GetChildren()` after `SetTopmost()` usually forces Flutter to publish semantics.

### Step 2 — Fill every input and click every non-destructive button once

Drive controls **by identity**, not by coordinates. UIA `Control.Click()` and
`SendKeys()` reach Flutter Windows widgets where synthetic mouse events do not.

```python
win = WindowControl(Name="<app window title>")
win.EditControl().SendKeys("000002")            # 请输入安全码 / safety code
win.ButtonControl(Name="验证登录").Click()        # 验证登录 / verify login
```

Then walk whatever dialogs appear. In the reported app the chain was:

```text
请输入安全码 + 验证登录  ->  确定 (OK)
  ->  用户协议: 同意并继续 (Agree and continue)
  ->  系统公告 (announcement; shows 授权有效期 / licence expiry)
  ->  main window (9 tabs)
```

### Step 3 — Only then attribute a cause

If reading and driving the whole screen still fails, now test the deep hypotheses —
proxy, ticket/hash, server binding, integrity, anti-debug — with the widget tree as
evidence rather than instead of it.

## Verification

The fix is verified when the pass/fail criterion holds: the UIA tree dump of the stuck
window lists an `EditControl` and a confirm `ButtonControl`, and filling the field +
invoking `Click()` advances the app to the next window. For this app that meant
reaching the main window (9 tabs) deterministically from a cold start, instead of
stalling on the safety-code page.

## Notes

- The general lesson is broader than licensing: **enumerate the visible controls before
  hypothesising about an invisible adversary.** A form waiting for input is the most
  common reason a screen "will not move".
- Flutter desktop apps expose a UIA tree on Windows, but often only after the
  accessibility/semantics layer is activated; an empty tree does not mean "no controls",
  it means "semantics not published yet".
- Prefer UIA `Control.Click()` over coordinate clicks for Flutter Windows targets; the
  coordinates can be correct while the click is still swallowed.
- Related: `lessons/contrib/ghidra-mcp-server-reverse-engineering.md` for the
  reverse-engineering tooling path when a UI walk genuinely is not enough.
