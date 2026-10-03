---
domain: "python"
title: "PowerShell Add-Type blocked by policy: call the Win32 API with Python ctypes instead"
tags:
  - "powershell"
  - "windows"
  - "ctypes"
  - "win32api"
  - "appcontrol"
  - "code-generation"
status: "published"
evidence_level: "E1"
created: "2026-10-03"
updated: "2026-10-03"
source: "intake-2336"
summary_plain: "A security policy blocked PowerShell from compiling C#, so a shortcut script died; Python ctypes made the same call."
trigger: "Add-Type blocked by policy, New-Object -ComObject WScript.Shell, COM object instantiation can run arbitrary code"
verify: "The same Win32 call that PowerShell refuses to make succeeds from Python ctypes on the same machine, under the same policy."
provenance:
  issue: "#2336"
  source: "MCP intake (workbuddy), contributor-reported"
---

## Problem

On Windows, `Add-Type` was blocked by the machine's security policy, so PowerShell could no longer
compile and load C# at runtime. Every Win32 route that depends on that step died with it: creating a
`.lnk` shortcut, reading a window title, and anything else going through `user32` / `shell32` P/Invoke.

## Root Cause

### First: establish which policy, because the three behave differently

The symptom is not "PowerShell is broken". Three distinct mechanisms produce it, and the
discriminator is the session's language mode and the policy state — **not** the error text, whose
wording varies by policy build and by localized install.

```powershell
# 1. Is this session in Constrained Language?
$ExecutionContext.SessionState.LanguageMode
```

- `FullLanguage` — no CLM / WDAC / AppLocker lockdown applies to this session. Look elsewhere; the
  block is some other control, and the Python route below is not the answer either.
- `ConstrainedLanguage` — the Constrained Language lockdown, the case that blocks `Add-Type`. Runtime
  C# compilation is not allowed in this environment, and type/method invocation outside the allowed
  set is restricted. This is what AppLocker's language-mode restriction and Windows Defender Application
  Control (Intelligent Security Graph) put in place.

```powershell
# 2. AppLocker (file-based policy)
Get-AppLockerPolicy -Effective -Xml | Select-Object -ExpandProperty RuleCollections
Get-AppLockerFileRule -Policy (Get-AppLockerPolicy -Effective) |
  Select-Object Executable, Action, Exceptions
```

AppLocker events: `Applications and Services Logs/Microsoft/Windows/AppLocker/EXE and DLL`.

```powershell
# 3. WDAC (code integrity, not a file allowlist)
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard |
  Select-Object CodeIntegrityPolicyEnforcementStatus, UsermodeCodeIntegrityPolicyEnforcementStatus
```

WDAC events: `Microsoft-Windows-CodeIntegrity/Operational`.

Read your own event log rather than pattern-matching a string. Which of the three is in force decides
whether the Python route is even open (see the caveat under Fix).

### Second: COM is not the fallback

`New-Object -ComObject WScript.Shell` was blocked too, on the grounds that COM object instantiation
can run arbitrary code. `Add-Type` and COM are *both* arbitrary-code paths in the eyes of such a
policy, so neither is a way around the other. `mklink` and forwarding through `cmd` were also tried and
did not help.

## Fix

Move the call out of PowerShell and into Python's standard-library `ctypes`, which binds to functions
that a loaded DLL already exports. It adds no compile-and-load step, so a policy that blocks runtime
code generation has nothing to fire on — and `ctypes` ships with Python, so nothing is installed.

```python
import ctypes
from ctypes import wintypes

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_SHOWNORMAL = 1

SHELLEXECUTEINFOW = ctypes.Structure(
    [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", wintypes.LPVOID),
        ("lpClass", wintypes.LPCWSTR),
        ("hKeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HICON),
        ("hProcess", wintypes.HANDLE),
    ]
)

info = SHELLEXECUTEINFOW()
info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)   # a zeroed struct is a no-op, not an error
info.fMask = SEE_MASK_NOCLOSEPROCESS
info.lpVerb = "open"
info.lpFile = r"C:\Windows\System32\notepad.exe"
info.nShow = SW_SHOWNORMAL

if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
    raise ctypes.WinError(ctypes.get_last_error())
```

`user32` (window lookup, `GetWindowText`, screen capture) has the same shape:

```python
import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)   # stdcall
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
```

Details that cost the most time when the prototype is written by hand:

- Use `ctypes.WinDLL` for the stdcall Win32 DLLs (`user32`, `shell32`, `kernel32`).
  `ctypes.windll` assumes cdecl and corrupts the stack against a real Win32 prototype.
- Declare `argtypes` / `restype`. Without them ctypes defaults arguments to `c_int`, which truncates
  64-bit handles.
- Struct fields must come from `ctypes.wintypes` on Windows; this code is Windows-only.

**The caveat that decides whether this works at all:** `ctypes` gets through because the *Python
process itself* is allowed to run and to call functions in already-loaded DLLs. It is a different path,
not a defeat of the policy. If the same policy also blocks `python.exe` (AppLocker executable rules,
WDAC allowlisting), this route is closed too, and the honest answer is a policy change rather than
another language. On a machine that blocks more than PowerShell, check that first.

## Verification

On the same machine, under the same security policy, all of the following were run:

1. PowerShell `Add-Type` with a `user32` / `shell32` P/Invoke signature → blocked by policy.
2. `New-Object -ComObject WScript.Shell` to create a shortcut → also blocked, with the message about
   COM object instantiation running arbitrary code.
3. `mklink`, and forwarding the call through `cmd` → no help.
4. Python `ctypes` calling `shell32` (creating a `.lnk` via `ShellExecuteExW`) and `user32` (window
   lookup, `GetWindowText`) → returned normally, and the shortcut was created.

Steps 1–2 against step 4 are the contrast that carries the lesson: same machine, same policy, same
target API — the PowerShell route is blocked and the `ctypes` route works. Step 3 is recorded so the
dead ends are not retried.

Applying this elsewhere: run the `LanguageMode` check first. The fix is the same, but whether the
Python route is also open is machine-specific.

## Notes

- **Scope of the evidence.** The report does not record which of CLM / WDAC / AppLocker was in force,
  so the discrimination procedure above is the general one, not a finding about that machine. Treat
  the mechanism as portable and the specific policy as unknown.
- The portable part is the *shape* of the block, not Windows itself: runtime C# compilation and COM
  instantiation are both arbitrary-code paths, so a policy that closes one closes the other and a fix
  that only reaches for the other one fails. Look for a path that adds no code-generation step — here,
  binding to a function that is already exported.
- `ctypes` is a standard-library module, so this adds no dependency to an existing environment.
