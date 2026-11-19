---
title: "A GUI window is named by its document's internal name, not by the folder you opened"
domain: "windows"
tags:
  - "gui-automation"
  - "window-title"
  - "identity"
  - "ocr"
  - "roboguide"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5163"
summary_plain: "按工位目录名找 GUI 主窗口永远落空：标题用的是工位文件里的内部名，跟目录改名无关；同前缀的模态错误框还会被认成主窗。"
trigger: "find window by folder name fails title shows another workcell name multiple instances z-order modal error dialog shares prefix OCR clicks wrong window"
verify: "Take the identity from the project file's stem and match the window title exactly. Matching the folder name finds nothing after a rename; a prefix match finds a modal dialog."
provenance:
  issue: "#5163"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

An automation looked for an application's main window by the **workcell directory name** and either
found nothing or found the wrong window: the title showed a different workcell name, and the OCR and
clicks that followed landed in the wrong place — which then looked like "the panel will not open" or
"the click does nothing". A modal error dialog, whose title also began with the application name, was
picked up as the main window more than once.

## Root Cause

The window title is the **document's own internal name**, and a cloned project keeps the internal name
of the original: the directory may be called `R558LAB`, while the project file inside it is
`B2_FE135R1_0524_MH` and the title is `ROBOGUIDE - B2_FE135R1_0524_MH` forever after. Renaming the
directory changes nothing about the title.

Two consequences, both mechanical: with several instances open, "the first window whose title starts
with the application name, in Z order" is a lottery; and every modal dialog the application raises
inherits the same prefix, so a prefix match cannot distinguish the main window from an error box.

## Fix

Take the identity from the thing that defines it, then match exactly:

```python
project = next(Path(workcell).glob("*.frw"))        # the document that owns the name
identity = project.stem                              # what the title will say, after any rename
title = f"APP - {identity}"

window = find_window(title_exact=title, exclude_dialogs=True)
if window is None:
    raise SystemExit(f"no main window for {identity}: {list_windows()}")
```

`exclude_dialogs` is not politeness: dialogs share the prefix, so "closest match" will eventually
click the error box that is trying to tell you something. And refusing loudly with the list of open
windows is worth more than a fallback, because the fallback is what clicks the wrong window.

## Verification

```console
$ python3 find_window.py --workcell R558LAB
identity: B2_FE135R1_0524_MH
window  : ROBOGUIDE - B2_FE135R1_0524_MH (hWnd 0x001A0C3E)
$ python3 find_window.py --workcell R558LAB --by-folder-name
no main window: folder name matches no title        <- the old behaviour, now stated
```

Before the fix the second command returned a window — usually the wrong one, sometimes a dialog.
