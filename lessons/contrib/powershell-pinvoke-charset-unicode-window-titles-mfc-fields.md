---
title: "PowerShell P/Invoke needs CharSet.Unicode to read window titles, and MFC AfxWnd fields ignore WM_SETTEXT"
domain: "windows"
tags:
  - "windows"
  - "powershell"
  - "pinvoke"
  - "win32-api"
  - "pywinauto"
  - "mfc"
  - "ui-automation"
  - "unicode"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "PowerShell 调 Win32 API 读窗口标题要 CharSet=Unicode；MFC 自绘控件不认 WM_SETTEXT，得像用户那样点一下再敲键。"
trigger: "EnumWindows returns 1-character titles like 8 / WM_SETTEXT succeeds but GetWindowTextW returns empty on a class AfxWnd100 control"
verify: "With CharSet=Unicode, EnumWindows returns intact Chinese captions; typing into the AfxWnd100 code field updates the sibling name Static, and WM_SETTEXT on qty/price updates the total Static."
source: "intake-3846"
provenance:
  issue: "#3846"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# PowerShell P/Invoke needs CharSet.Unicode to read window titles, and MFC AfxWnd fields ignore WM_SETTEXT

## Problem

The goal was automating a broker's native Win32 trade dialog — an MFC form with code / price /
quantity inputs. Three failures arrived in sequence on Windows 11 with PowerShell 5.1.

**1. `pip install pywinauto` hung.** No output for more than five minutes, the pid burning roughly
340 seconds of CPU, `site-packages` still empty, no traceback, no error at the end because there was
no end. The install was killed.

**2. Window enumeration returned unreadable text.** Driving the app with `Add-Type` P/Invoke instead
of pywinauto, `EnumWindows` / `EnumChildWindows` produced one-character titles (`"8"`, class `"#"`)
or garbled Chinese where the app visibly shows a normal caption.

**3. `WM_SETTEXT` "succeeded" and nothing happened.** `SendMessage(h, WM_SETTEXT, ...)` on the code,
price and quantity fields returned without error, but `GetWindowText` read back `""` and nothing
appeared on screen. The code field's class is `AfxWnd100`, a custom-drawn MFC control, not a real
`Edit`.

The reported error text, verbatim:

```
pip install pywinauto: no output, 340s CPU, site-packages still empty
GetWindowTextW returns 1-char/garbled titles
WM_SETTEXT on custom MFC AfxWnd100 field silently no-ops and GetWindowText returns ""
```

## Root Cause

**The `W` entry point is not the same thing as Unicode marshalling.** `GetWindowTextW` and
`GetClassNameW` were called correctly, but the `DllImport` declarations omitted
`CharSet = CharSet.Unicode`. The runtime then marshals the `StringBuilder` buffer as ANSI, so the
wide-character data the API writes is decoded as single-byte text: every title collapses to one
character or to mojibake. Choosing the `W` suffix in the function name does not change the
marshalling; the declaration does.

**`AfxWnd100` is a custom-drawn MFC control, and `WM_SETTEXT` is not its input path.** A plain
`Edit` implements `WM_SETTEXT`; a custom control that draws its own content has no reason to handle
that message, so the send returns success (the message was delivered) while the control discards it.
"SendMessage returned" only means delivery, never that the value took. That is why the read-back was
`""` with no error anywhere: the failure is a no-op, not an exception.

**The `pip install` hang is undiagnosed in the report.** The intake records the symptom (no output,
high CPU, empty `site-packages`) but no `pip -v` / `-vvv` log, no index URL and no network context,
so the cause was not established — the reporter's next step was to stop depending on pywinauto and
drive the app through P/Invoke directly. Treat the hang as unresolved rather than as "pywinauto is
broken": it is not established whether the resolver, the wheel download or the local build was
responsible.

## Solution

**1. Declare Unicode marshalling on every wide-character import.**

```powershell
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int count);

  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern int GetClassNameW(IntPtr hWnd, StringBuilder text, int count);

  [DllImport("user32.dll")]
  public static extern int EnumWindows(EnumProc cb, IntPtr lParam);
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern int EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern int GetDlgCtrlID(IntPtr hWnd);

  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern IntPtr SendMessage(IntPtr hWnd, uint msg, IntPtr wParam, string lParam);
}
"@
```

**2. Map controls by dialog-control ID, never by index or screen position.**

```powershell
# Collected with EnumWindows + EnumChildWindows + GetDlgCtrlID
# code 12005 / price 12006 / qty 12007 / submit 2010
```

Enumeration order and pixel positions both move when the app redraws; the control ID is the
hand-maintained contract the app itself uses.

**3. A plain `Edit` takes `WM_SETTEXT` (`0x000C`).**

```powershell
[Win32]::SendMessage($priceEdit, 0x000C, [IntPtr]::Zero, "3.00") | Out-Null
```

**4. A custom-drawn field (`AfxWnd100`) has to be focused like a user would focus it.** Clicking the
parent window is not enough — the click has to land inside the control itself:

```powershell
# SetForegroundWindow(top) -> GetWindowRect(ctrl) -> SetCursorPos(center)
# -> mouse_event(0x0002) -> mouse_event(0x0004) -> SendKeys
```

**5. Click a button by sending `BM_CLICK` (`0x00F5`) to its handle.**

```powershell
[Win32]::SendMessage($submit, 0x00F5, [IntPtr]::Zero, $null) | Out-Null
```

**6. When the inputs are unreadable, verify through the app's own derived values.** Match an
auto-populated sibling `Static` (the stock name derived from the code) to confirm the code field
actually took the ticker, and compare an auto-computed total (`qty x price`). After the submit
click, re-read that total: **cleared means submitted; unchanged means the click did not take** —
usually because a modal confirmation dialog is waiting.

**7. A tab strip may simply not be scriptable.** `BM_CLICK` on the tab buttons and the app's
`F9`/`F10` hotkeys both failed; the hotkeys belong to the main frame window, not to the dialog. Read
the submit button's caption (`Buy` / `Sell`) to confirm the active tab, and abort with a human
instruction instead of guessing which side of the market the order went to.

## Verification

The reporter's live check, on a broker trade client, Windows 11 + PowerShell 5.1 — not reproduced in
this repository:

- After adding `CharSet = CharSet.Unicode`, Chinese window titles and class names came back intact
  and the controls mapped cleanly by `GetDlgCtrlID` (code `12005`, price `12006`, qty `12007`,
  submit `2010`).
- A real order form was filled: the code field was clicked, the ticker typed, and the adjacent name
  `Static` updated to the expected stock name; `WM_SETTEXT` on price and qty then made the
  auto-computed amount `Static` show exactly `7425.00` = `2.97 x 2500`, confirmed by screenshot.
- Submit click followed by re-reading the amount `Static` distinguishes "submitted" (cleared) from
  "blocked by a confirm dialog" (unchanged).

The discriminating check for the marshalling half is cheap and worth running first: enumerate the
same window twice, once with `CharSet.Unicode` and once without, and compare the returned caption
lengths. A title of length 1 where the app shows several characters is the marshalling bug, not an
empty window.

## Notes

- Evidence E1: single contributor report, reproduced by the reporter on their own machine only. No
  broker name, no application version and no full script are recorded in the intake.
- The `pip install pywinauto` hang was **not** diagnosed. If it reproduces, capture
  `pip install -vvv pywinauto` and the configured index URL before concluding anything about the
  package.
- The no-op is the dangerous half: `SendMessage` returning success is evidence that the message was
  delivered, not that the control accepted it. Any automation that writes through messages should
  read a value back that the app itself computes, because a custom control will not echo the value.
- Sibling lesson: `lessons/contrib/powershell-add-type-blocked-use-python-ctypes-instead.md` covers
  the case where `Add-Type` itself is blocked by policy and `python -c` with `ctypes` is the way in.
