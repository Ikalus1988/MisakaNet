---
domain: "windows"
title: "PowerShell curl alias conflicts with Invoke-WebRequest"
verification: "metadata-normalized"
---
---{"title": "PowerShell curl alias conflicts with Invoke-WebRequest", "domain": "windows", "tags": ["powershell", "curl", "invoke-webrequest", "alias"]}---

## Problem

Running `curl` in PowerShell silently uses `Invoke-WebRequest` instead of real curl, causing unexpected behavior with API calls.

## Root Cause

PowerShell defines `curl` as a built-in alias for `Invoke-WebRequest`, which has a completely different syntax and output format than the real curl executable.

## Fix

Use `curl.exe` instead of `curl` in PowerShell to explicitly invoke the real curl binary. Alternatively, remove the alias with `Remove-Item alias:curl -Force`.

## Verification

Run `Get-Alias curl` in PowerShell. It returns `curl -> Invoke-WebRequest`. Then run `curl.exe --version` to confirm the real curl is accessible.
