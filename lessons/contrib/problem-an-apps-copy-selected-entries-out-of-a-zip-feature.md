---
title: "自研 ZIP 读取器校验了条目，却漏了复制路径的第二次解压"
domain: "development"
tags:
  - "problem"
  - "an"
  - "app"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4017"
summary_plain: "自研 ZIP 读取器校验了条目，却漏了复制路径的第二次解压"
trigger: "自研 ZIP 读取器校验了条目，却漏了复制路径的第二次解压"
verify: "Test archive with an entry named `*` plus `ok.txt` plus a 1000:1 ratio entry: copying out `ok.txt` must leave only `ok.txt` in the temp folder, and the `*` entry must be refused. `unzip -qq a.zip -d…"
provenance:
  issue: "#4017"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

An app's "copy selected entries out of a ZIP" feature validated entries in its own ZIP reader (refusing ../ paths, symlinks, encrypted entries and compression-ratio bombs), then extracted with `ditto -x -k archive tmp`. Every entry was extracted, so none of the guards applied. The fix switched to `unzip -qq archive -d tmp name1 name2 ...` with only the vetted names, but that was still unsafe.

## Root Cause

1) `ditto -x -k` (and `unzip` with no names) extract the whole archive: checks that only filter the UI listing protect nothing. 2) Info-ZIP `unzip` treats each name argument as a wildcard pattern (`*`, `?`, `[...]`; backslash escapes), so a vetted entry literally named `*` makes it extract every entry. 3) macOS's Info-ZIP `unzip` does not accept `--` as an end-of-options marker: it matches `--` as a literal name and exits 11. So a name starting with `-` can be read as an option.

## Fix

Pass only the vetted, selected entry names to `unzip`, as separate argv items with no shell. Refuse to extract (mark as not copyable) any entry whose path contains `* ? [ ] \` or has a component starting with `-`. After extraction, `lstat` every result and reject symlinks or any path that resolves outside the temp folder. Delete the temp folder afterwards.

## Verification

Test archive with an entry named `*` plus `ok.txt` plus a 1000:1 ratio entry: copying out `ok.txt` must leave only `ok.txt` in the temp folder, and the `*` entry must be refused. `unzip -qq a.zip -d out -- ok.txt` exits 11 on macOS, which shows that `--` is not supported.
