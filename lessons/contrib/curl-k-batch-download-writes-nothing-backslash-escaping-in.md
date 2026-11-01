---
title: "curl -K batch download writes nothing: backslash escaping in the config file plus missing --create-dirs"
domain: "devops"
tags:
  - "curl"
  - "windows"
  - "download"
  - "escaping"
  - "parallel"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4216"
summary_plain: "A batch download driven by `curl --parallel --create-dirs -K urls.txt` fetched ~80 files and reported exit code 0 (or…"
trigger: "curl -K batch download writes nothing: backslash escaping in the config file plus missing --create-dirs. A batch download driven by `curl --parallel…"
verify: "1) Resulting file count equals the manifest count. 2) Every file byte size equals the size reported by the source (API or tree listing). 3) Re-running the same command is idempotent and changes no…"
provenance:
  issue: "#4216"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A batch download driven by `curl --parallel --create-dirs -K urls.txt` fetched ~80 files and reported exit code 0 (or only `curl: (23) client returned ERROR on write`), yet the destination directory stayed empty. Each config entry looked like `output = "C:\Users\<user>\out\file.bin"`.

## Root Cause

Two independent causes in the same run. (1) Inside a curl config file a backslash in a quoted value is an escape character, so a Windows path is mangled into a path curl cannot open. (2) Even with a valid path, curl does not create missing directories unless --create-dirs is passed. With --parallel a per-transfer failure does not abort the run, and the exit status alone does not reveal that nothing was written.

## Fix

Use forward slashes in every config path (`C:/Users/<user>/out/file.bin`), add --create-dirs, and run one single-file transfer before switching to --parallel. Afterwards reconcile the result against an expected manifest (name -> byte size) instead of trusting the exit code.

## Verification

1) Resulting file count equals the manifest count. 2) Every file byte size equals the size reported by the source (API or tree listing). 3) Re-running the same command is idempotent and changes no sizes.
