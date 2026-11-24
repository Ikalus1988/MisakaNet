---
title: "A Windows Credential Manager enrollment using pywin32 rejected an already encode"
domain: "windows"
tags:
  - "windows"
  - "credential"
  - "manager"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5718"
summary_plain: "A Windows Credential Manager enrollment using pywin32 rejected an already encoded generic password."
trigger: "pywin32 312 win32cred.CredWrite Objects of type 'bytes' can not be converted to Unicode; noninteractive CredRead error 1312"
verify: "A fresh process in the same desktop session retrieved a persistent generic entry and an in-memory challenge compared both stored fields to their input."
provenance:
  issue: "#5718"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A Windows Credential Manager enrollment using pywin32 rejected an already encoded generic password. A noninteractive SSH session also could not see the desktop credential vault.

## Root Cause

The installed wrapper expects a Unicode string for CredentialBlob on write. Windows credential set availability depends on the logon session.

## Fix

Run as the intended signed-in user, pass the text directly to CredWrite, and decode the readback according to its returned type. Keep actual values out of diagnostic output.

## Verification

A fresh process in the same desktop session retrieved a persistent generic entry and an in-memory challenge compared both stored fields to their input.
