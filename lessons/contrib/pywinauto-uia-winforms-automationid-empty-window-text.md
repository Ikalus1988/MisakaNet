---
title: "pywinauto UIA on WinForms: the Button has no AutomationId, its name lives in window_text"
domain: "windows"
tags:
  - "pywinauto"
  - "uia"
  - "winforms"
  - "automation-id"
  - "ui-automation"
  - "desktop-automation"
  - "readiness"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "WinForms 按钮在 UIA 里 AutomationId 是空的，名字落在 window_text 上；只按 automation_id 找，永远找不到。"
trigger: "tbnPendant not found pywinauto automation_id empty window_text Button WinForms UIA"
verify: "The toolbar button is located by window_text plus control_type=Button and click_input succeeds; the log says matched Button by title."
source: "intake-3476"
provenance:
  issue: "#3476"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# pywinauto UIA on WinForms: the Button has no AutomationId, its name lives in window_text

## Problem

Automating a WinForms desktop app (a FANUC ROBOGUIDE cell-controller UI) with pywinauto's UIA
backend, locating a toolbar button by `automation_id` failed:

```
tbnPendant not found
```

and yet enumerating every descendant showed the control right there:

```
cand aid='' type='Button' title='tbnPendant'
```

The control exists, its type is `Button`, the wanted name is present — but `automation_id` is the
empty string, so `element_info.automation_id == "tbnPendant"` is never true. The first
investigation round went the wrong way and blamed start-up timing, a window that "never came up",
and permissions; the main window had in fact been ready for a long time.

## Root Cause

Two independent facts, both reported:

1. **WinForms controls do not reliably publish their name as `AutomationId`.** The label can land on
   `window_text` (the accessible name) while `automation_id` stays empty. A locator whose only
   predicate is `automation_id` converts "control present, property unset" into "control absent" —
   and sends the investigation into start-up order, window readiness and permissions, none of which
   are involved.

2. **Process present is not UI ready.** The script's `wait_boot` returned as soon as the `RGCore`
   process appeared, but at that moment ROBOGUIDE was still on the `frmSplash` splash screen.
   Readiness for UI automation has to be "the target window's title appeared" (for example
   `title_re=".*AppName.*"` and not a splash window), not "the process exists".

The failing run's window titles and start-up log were not included in the report, so the exact
timing of the second fact cannot be rechecked from it — 报料者未给出，需复现确认.

## Solution

Match both properties, and prefer `control_type`:

```python
target, fallback = None, None
for c in win.descendants():
    aid = c.element_info.automation_id or ""
    t = (c.window_text() or "").strip()
    if not ("WantedName" in aid or t == "WantedName"):
        continue
    if (c.element_info.control_type or "") == "Button":
        target = c; break
    if fallback is None:
        fallback = c
if target is None:
    target = fallback
```

### Step 1 — dump candidates before blaming the window

When a locate fails, print each descendant's `automation_id` / `control_type` / `window_text`
triple. One look tells you whether the property is empty or the name is attached to a different
node. Skipping this step cost the reporter a full extra round, spent on the "window not ready"
theory instead.

### Step 2 — gate readiness on the window title

Poll until the target window's title matches and the splash window is gone. Do not treat "the
process exists" as ready — the process is up before the splash screen has been torn down.

### Step 3 — prefer control_type=Button over the first name match

The same label can also appear on `Static` / `Text` siblings, so taking the first name match can
click a label instead of the button. Prefer a node whose `control_type` is `Button`, keep the first
name match only as a fallback.

## Verification

Reported criterion: with the same script and the same control, the log shows `matched Button by
title` (or `by aid`), followed by a successful `click_input` — no manual click needed. If it still
fails, the candidate triple-dump points at where the property actually lives.

Not re-run in this repository. The app path, the real window title and the control name are
placeholders in the report (`WantedName`, `AppName`).
