---
title: "Writing DSH profile package.json with PowerShell UTF8 BOM resets the whole plugin profile"
domain: "windows"
tags:
  - "dsh"
  - "json"
  - "bom"
  - "powershell"
  - "profile"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3784"
summary_plain: "After editing a DSH profile package.json with PowerShell (Set-Content -Encoding UTF8), restarting DSH comes up with…"
trigger: "Writing DSH profile package.json with PowerShell UTF8 BOM resets the whole plugin profile. After editing a DSH profile package.json with PowerShell…"
verify: "First bytes of the file are \"{\" (0x7B) and DSH keeps all plugins after a restart."
provenance:
  issue: "#3784"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

After editing a DSH profile package.json with PowerShell (Set-Content -Encoding UTF8), restarting DSH comes up with every plugin gone - the profile looks like it was reset.

## Root Cause

Windows PowerShell 5.1 writes UTF-8 with a BOM, and the host JSON parser refuses a file whose first bytes are EF BB BF, so it falls back to a fresh default profile.

## Fix

Never rewrite DSH JSON with PowerShell Set-Content. Use Node fs.writeFileSync(path, JSON.stringify(obj, null, 2), "utf8") which writes no BOM, and verify the first three bytes are not EF BB BF afterwards.

## Verification

First bytes of the file are "{" (0x7B) and DSH keeps all plugins after a restart.
