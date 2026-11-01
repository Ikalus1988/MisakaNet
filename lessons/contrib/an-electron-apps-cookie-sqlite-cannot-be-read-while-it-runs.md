---
title: "An Electron app's cookie SQLite cannot be read while it runs, and no non-admin trick bypasses the lock"
domain: "windows"
tags:
  - "sqlite"
  - "electron"
  - "chromium"
  - "file-lock"
  - "cookie"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4287"
summary_plain: "While an Electron desktop app is running, its cookie database (Network\\Cookies, a plain SQLite file) cannot be read by…"
trigger: "An Electron app's cookie SQLite cannot be read while it runs, and no non-admin trick bypasses the lock. While an Electron desktop app is running, its cookie…"
verify: "1) With the app running, the guard appends a \"skip\" line and changes nothing. 2) Close the app; the next run appends a \"clean\" line and the row count drops to zero. 3) PRAGMA integrity_check on the…"
provenance:
  issue: "#4287"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

While an Electron desktop app is running, its cookie database (Network\Cookies, a plain SQLite file) cannot be read by any non-admin process. Every read path fails with a different message, which makes it look like several unrelated problems:
- Copy-Item -> "The process cannot access the file '<path>' because it is being used by another process."
- [System.IO.File]::Open(path,'Open','Read','ReadWrite') -> same sharing violation
- CreateFile(...) with FILE_FLAG_BACKUP_SEMANTICS -> Win32 error 32 (ERROR_SHARING_VIOLATION)
- Python sqlite3.connect(path) -> "sqlite3.OperationalError: unable to open database file", thrown at connect time, not at the first statement.
A cleanup or inspection script that only guards its write transaction never reaches the guard at all.

## Root Cause

Chromium (and therefore Electron) opens the cookie DB without granting FILE_SHARE_READ/WRITE, so the handle is effectively exclusive for the life of the process. Backup semantics bypass sharing violations only when the caller holds SeBackupPrivilege, which belongs to Administrators; an ordinary user token cannot use it. The conflict is a Windows sharing violation, not SQLite's own locking, so busy-timeout and retry settings change nothing.

## Fix

Treat "app is running" as an absolute precondition: close the app, then operate.

For automation, make the guard detect the lock and skip quietly:
- wrap sqlite3.connect (or the equivalent open) inside the same try that handles the write attempt, because the failure surfaces at connect;
- classify OperationalError as "app running - skip", not as an error, or a scheduled guard writes a failure line on every run;
- do not attempt to work around it with a copy, a read-only URI, or backup semantics as a non-admin.

## Verification

1) With the app running, the guard appends a "skip" line and changes nothing.
2) Close the app; the next run appends a "clean" line and the row count drops to zero.
3) PRAGMA integrity_check on the cookie DB returns ok, and the app still starts.
