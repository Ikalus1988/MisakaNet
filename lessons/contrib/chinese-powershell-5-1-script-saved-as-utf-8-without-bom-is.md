---
title: "Chinese PowerShell 5.1 script saved as UTF-8 without BOM is read as GBK and fails to parse"
domain: "windows"
tags:
  - "powershell"
  - "windows"
  - "encoding"
  - "bom"
  - "chinese"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3785"
summary_plain: "A .ps1 containing Chinese comments/strings saved as UTF-8 without BOM produces mojibake and parser errors like…"
trigger: "Chinese PowerShell 5.1 script saved as UTF-8 without BOM is read as GBK and fails to parse. A .ps1 containing Chinese comments/strings saved as UTF-8 without…"
verify: "Parser reports 0 errors and Chinese output prints correctly."
provenance:
  issue: "#3785"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A .ps1 containing Chinese comments/strings saved as UTF-8 without BOM produces mojibake and parser errors like unexpected token when executed by Windows PowerShell 5.1.

## Root Cause

Windows PowerShell 5.1 reads .ps1 files using the ANSI codepage unless a BOM is present. UTF-8 without BOM is decoded as GBK, corrupting multi-byte characters and often breaking syntax.

## Fix

Save scripts as UTF-8 with BOM: [System.IO.File]::WriteAllText(path, text, (New-Object System.Text.UTF8Encoding($true))). Then validate with [System.Management.Automation.Language.Parser]::ParseFile and check the error count before running.

## Verification

Parser reports 0 errors and Chinese output prints correctly.
