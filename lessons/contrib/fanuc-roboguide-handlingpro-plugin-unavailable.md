---
{
  "provenance": {"source": "intake", "issue": "#3276"},
  "domain": "fanuc",
  "title": "ROBOGUIDE HandlingPRO 'plugin unavailable': a missing install feature, not COM registration",
  "tags": [
    "fanuc",
    "roboguide",
    "handlingpro",
    "installshield",
    "dotnet-assembly",
    "windows",
    "plugin",
    "file-association"
  ],
  "status": "published",
  "evidence_level": "E1",
  "summary_plain": "ROBOGUIDE can't open a HandlingPRO workcell because the installer feature was never selected, not a COM issue.",
  "trigger": "ROBOGUIDE plugin unavailable HandlingPRO.HPCPlugIn RGCore crash workcell",
  "verify": "HandlingPRO.exe/.dll exist in bin/ and RGCore stays alive past splash; regsvr32 on the .NET HandlingPRO.dll reports no DllRegisterServer."
}
---

# ROBOGUIDE HandlingPRO 'plugin unavailable': a missing install feature, not COM registration

## Problem

A ROBOGUIDE (FANUC) HandlingPRO workcell fails to open, or opens and crashes, reporting that the primary plugin is unavailable. The workcell's `<PlugIns>` block names `HandlingPRO.HPCPlugIn`, and the first instinct is a broken COM registration (`PrimaryPlugInProgID="HandlingPRO.HPCPlugIn"`), so the debugging effort goes into `regsvr32` and `RegAsm` registration. That is the wrong path, and it burns a lot of time before the real cause is visible.

The reported symptom is a workcell (for example `B2_FE135R1_0524_MH`) that will not launch; the host process `RGCore.exe` dies or hangs at the splash with a "plugin unavailable" error.

## Root Cause

There are **two independent necessary conditions**, and both must be fixed:

1. **The installer feature was never installed.** HandlingPRO is a distinct InstallShield feature under `[HandlingPRO]` in the setup's `Control.ini` — a sibling of `WeldPRO` and `PaintPRO`, not part of the core. A "reinstall" that only restores core ROBOGUIDE plus FRVRC copies **no plugin payload at all**, yet `setup.exe` still exits `0`, so the install looks successful. A file-copy "success" is not a feature-complete install.

2. **The `<PlugIns>` entries are .NET class full names, not COM ProgIDs.** RGCore resolves them by loading assemblies from its own `bin/` directory. This is why registry inspection finds nothing:

   - `HandlingPRO.dll` is a .NET assembly (v9.40179.0.4) with **no `DllRegisterServer`**, so `regsvr32` is meaningless ("module loaded but entry-point not found").
   - `RegAsm HandlingPRO.dll /regfile` shows the ProgID it *would* write is `HPCPlugIn_NET.HPCPlugIn` — never `HandlingPRO.HPCPlugIn`. The name in the workcell is not a ProgID lookup key.
   - The real launcher contract is the `.frw` file association: `.frw=frwFile` -> `HandlingPRO.exe /W "%1"`. A missing `HandlingPRO.exe` is the direct crash cause.

### Judgment criteria for others hitting this

- If the vendor binary has **no `DllRegisterServer`** and is a **.NET assembly**, stop looking at `HKCR` ProgIDs. Check whether the host resolves types by assembly name from its own directory instead.
- If the app's file association for the document type points at a **product-specific `.exe`**, that `.exe` *is* the plugin/launcher — its absence is the failure.
- Distinguish a file-copy "success" from a feature-complete install by reading the installer's `Control.ini` feature sections, not by whether `setup.exe` exited `0`.

## Solution

Perform a **Modify install** with the HandlingPRO feature actually selected, then launch through the `.frw` association.

1. Re-run the ROBOGUIDE installer and choose **Modify** (not Repair, and not a core-only repair).
2. Under the optional features, tick **HandlingPRO** (its siblings `WeldPRO` / `PaintPRO` are separate — selecting ROBOGUIDE + FRVRC alone copies no plugin payload).
3. Confirm the plugin payload landed: `HandlingPRO.exe` and `HandlingPRO.dll` must now exist under ROBOGUIDE's `bin/`.
4. Launch the workcell through the document association (`HandlingPRO.exe /W "<workcell>.frw"`) rather than expecting a bare RGCore start to find the plugin.

### If it still blocks after the fix

A separate **evaluation-license expiry** dialog ("Evaluation - (Expired)") can freeze the workcell at `frmSplash` with CPU and memory frozen and no crash dump. That is a **licensing gate, not a plugin failure** — do not confuse the two. Check the license before re-opening the COM investigation.

## Verification

1. `HandlingPRO.exe` and `HandlingPRO.dll` are present in ROBOGUIDE's `bin/`.
2. `regsvr32 HandlingPRO.dll` confirms there is no `DllRegisterServer` — i.e. registration is not the mechanism, so the absence of a ProgID does not indicate a broken install.
3. The workcell `B2_FE135R1_0524_MH` launches and `RGCore.exe` persists past its splash with no `WerFault` restart.
4. No "plugin unavailable" error; the plugin classes resolve from `bin/`.

```powershell
# Confirm the plugin payload exists
Get-ChildItem "$env:ProgramFiles\FANUC\ROBOGUIDE\bin" -Filter 'HandlingPRO.*' |
  Select-Object Name, Length

# Launch via the .frw association contract
Start-Process 'HandlingPRO.exe' -ArgumentList '/W', '"<workcell>.frw"'
```

## Notes

- `.frw` is the document type; its association (`.frw=frwFile` -> `HandlingPRO.exe /W "%1"`) is what actually selects and loads the product plugin. Launching the host alone does not.
- A failed `regsvr32` on `HandlingPRO.dll` is *expected* on a .NET assembly and is not evidence of a broken install.
- `setup.exe` exit code `0` only proves the installer ran; feature selection is what determines whether the plugin payload was copied.
- Related: `fanuc-rgcore-hang-endpoint-security-injection` covers a different RGCore-at-splash failure (endpoint-security DLL injection), which is a separate root cause from this missing-feature one.
