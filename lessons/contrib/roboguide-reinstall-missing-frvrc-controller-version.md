---
title: "ROBOGUIDE won't open a workcell after reinstall: the FRVRC version its BackupVersion names is missing"
domain: "fanuc"
tags:
  - "fanuc"
  - "roboguide"
  - "frvrc"
  - "virtual-controller"
  - "reinstall"
  - "workcell"
  - "backupversion"
  - "registry"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "ROBOGUIDE 重装后工作单元打不开，是只装了主程序，没装工作单元 BackupVersion 指定的那个版本的虚拟控制器 FRVRC。"
trigger: "ROBOGUIDE workcell will not open after reinstall controller version mismatch BackupVersion V9.40P/74/None FRVRC"
verify: "grep BackupVersion *.frw names a version, Shared/Off Line/FRVRC/<version>/Bin holds FRSock/pmon/httpd/proxy/telnet/rpcm/syutl, and the Uninstall InstallLocation is the real install root."
source: "intake-3249"
provenance:
  issue: "#3249"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# ROBOGUIDE won't open a workcell after reinstall: the FRVRC version its BackupVersion names is missing

## Problem

After uninstalling and reinstalling ROBOGUIDE, a workcell (`.frw`) that used to open no longer does: the
workcell will not open, or the virtual controller never comes up. The installer reported success and the
uninstall registry key is present, so "is it installed?" answers yes — but launching the workcell fails
on a controller **version mismatch**.

The verbatim mismatch dialog is not in the report — 报料者未给出，需复现确认. What the reporter does give:

- the main installer finished and reported success;
- uninstall registry entries exist, so the install looks complete;
- the workcell then fails at run time on the controller version, not on a missing file.

## Root Cause

A workcell is bound to one virtual controller release, and the binding is written inside the `.frw`:

```text
BackupVersion="V9.40P/74/None"
```

That field names the FRVRC release the workcell was built against (here `V9.40`), and the workcell can
only start that version. On the install media the FRVRC releases ship as **separate** installers, one
`setup.exe` per version — `FRVRC770`, `FRVRC820`, … `FRVRC940` — and the main ROBOGUIDE install does not
necessarily install all of them. A reinstall that takes only the default main-program feature set
therefore leaves the version this workcell needs uninstalled. Nothing is corrupt; the dependency is
simply absent.

A second, independent trap: the install root can move (for example from the default
`C:\Program Files (x86)\FANUC` to `D:\<install root>\roboguide`). Registry entries from the old install
can survive and still point at the old path, so "the registry has an entry" is not evidence that the
install being launched is the one that was just written.

## Solution

1. Read the required controller version out of the workcell instead of guessing:

   ```bash
   grep BackupVersion *.frw
   ```

   A value like `V9.40P/74/None` names the FRVRC release (`V9.40`); the report does not break the trailing
   fields down — 报料者未给出，需复现确认.

2. Install *that* release from the same media the main program came from: run
   `FRVRC940\setup.exe` (the directory is named after the release). The workcell names one version;
   a later FRVRC does not satisfy it.

3. Confirm the controller modules landed:

   ```bash
   ls "Shared/Off Line/FRVRC/V9.40/Bin"
   ```

   The key modules are `FRSock.dll`, `pmon.dll`, `httpd.dll`, `proxy.dll`, `telnet.dll`, `rpcm.dll`,
   `syutl.dll`.

4. Point the uninstall entry at the install root actually in use:

   ```bat
   reg query "HKLM\SOFTWARE\...\Uninstall\<ROBOGUIDE entry>" /v InstallLocation
   ```

   If it still names the old root, repair/reinstall so it names the new one.

5. Licensed PRO plugins: a `bin\zh` folder that carries `.resources.dll` but no matching main `.exe` means
   the option's licence was not released. That is the normal licence gate, not a broken install — handle
   it through the official licensing channel.

## Verification

All four checks must pass, in this order:

1. `grep BackupVersion *.frw` prints the version the workcell needs;
2. `ls "Shared/Off Line/FRVRC/"` lists a `V9.<n>` directory matching that version;
3. that directory's `Bin` contains `FRSock.dll`, `pmon.dll`, `httpd.dll`, `proxy.dll`, `telnet.dll`,
   `rpcm.dll`, `syutl.dll`;
4. the Uninstall `InstallLocation` names the install path in use.

When 1–4 hold, the workcell opens and the virtual controller starts. If it still reports a version
mismatch, compare step 1's version with step 2's directory name — a `V9.30` workcell against a `V9.40`
install is the same failure with a different pair of numbers.

## Notes

- The report does not name the ROBOGUIDE build, the FRVRC media build, or the verbatim mismatch dialog —
  报料者未给出，需复现确认.
- The workcell's `BackupVersion` is authoritative. ROBOGUIDE's own build number is the *simulator* build,
  not the controller release, and cannot substitute for it.
- Related: `lessons/contrib/fanuc-frvrc-auto-backup-illegal-path.md` covers FRVRC auto-backup path
  failures (FILE-077 / FILE-079 / FILE-031) — a different failure in the same subsystem.
