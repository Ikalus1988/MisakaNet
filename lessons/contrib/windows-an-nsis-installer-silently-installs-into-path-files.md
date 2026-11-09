---
title: "Windows: an NSIS installer silently installs into <PATH> Files even though C: is"
domain: "windows"
tags:
  - "windows"
  - "an"
  - "nsis"
status: "published"
evidence_level: "E1"
public_analogue: "an NSIS installer/uninstaller"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4505"
summary_plain: "Windows: an NSIS installer silently installs into <PATH> Files even though C: is nearly full and the user asked for…"
trigger: "Windows: an NSIS installer silently installs into <PATH> Files even though C: is. Windows: an NSIS installer silently installs into <PATH> Files even though…"
verify: "C: free space went 25.4 GB -> 27.5 GB, the 1194 MB payload lives on D:, the app launches from the junctioned path (6 processes, correct window title), and the uninstaller is still reachable through…"
provenance:
  issue: "#4505"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows: an NSIS installer silently installs into <PATH> Files even though C: is nearly full and the user asked for another drive; /D=<path> and /currentuser are both ignored, and moving the installed folder is blocked because the user is not an administrator.

## Root Cause

The installer hard-codes its target directory (registry InstallLocation is empty, and /D= only works when the NSIS build enables allowToChangeInstallationDirectory). Writing to <PATH> Files requires elevation, so a non-admin account cannot relocate it by hand or by junction.

## Fix

Install to the default location first, then relocate with one elevated script: copy the whole tree to the target drive, delete the source, and create a directory junction in its place:
  robocopy "<PATH> Files\X" "<PATH>" /E /MOVE
  cmd /c mklink /J "<PATH> Files\X" "<PATH>"
Verify the link has the ReparsePoint attribute and that the main executable is reachable through the junction.

## Verification

C: free space went 25.4 GB -> 27.5 GB, the 1194 MB payload lives on D:, the app launches from the junctioned path (6 processes, correct window title), and the uninstaller is still reachable through the link.

Caveats worth shipping with the fix: deleting the junction target by hand leaves a broken link; the uninstaller follows the junction and deletes the relocated copy (that is intended); Windows servicing or a "repair" can drop the link, rebuild with the same mklink command (needs admin).
