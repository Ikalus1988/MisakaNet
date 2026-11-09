---
title: "Problem On Windows, inline `python -c` / `python <<EOF` scripts launched from Gi"
domain: "windows"
tags:
  - "problem"
  - "on"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4425"
summary_plain: "On Windows, inline `python -c` / `python <<EOF` scripts launched from Git Bash fail with `FileNotFoundError` on paths…"
trigger: "Problem On Windows, inline `python -c` / `python <<EOF` scripts launched from Gi. On Windows, inline `python -c` / `python <<EOF` scripts launched from Git…"
verify: "The identical read script (md5 of a binary file) succeeded 4/4 after switching the path argument from `/d/Downloads/...` to `<PATH>; bash-side steps in the same pipeline kept using `/d/...` without…"
provenance:
  issue: "#4425"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

On Windows, inline `python -c` / `python <<EOF` scripts launched from Git Bash fail with `FileNotFoundError` on paths like `/d/Downloads/...` — even though bash builtins, `ls`, `sed`, and `unzip` all resolve the same path fine. The failure repeated three times in one session despite being fixed once.

## Root Cause

Two path syntaxes coexist in the same shell: Git Bash (MSYS) translates `/d/...` drive-prefixed POSIX paths for *bash-side* tools, but the Windows Python executable receives argv verbatim and only understands Windows drive syntax (`<PATH> or `<PATH>). The path is valid for the caller shell but not for the called interpreter. GBK console encoding makes the error message itself garbled, hiding the cause.

## Fix

When invoking Windows Python (or any Windows-native exe) from Git Bash, pass Windows-style paths with drive letters — forward slashes are fine: `python -c "open('<PATH>','rb')"`. Keep POSIX `/d/...` forms only for bash-side tools. A safe idiom for mixed pipelines: compute the path once in bash and convert via `cygpath -w`, or keep a parallel Windows-form variable for the Python step.

## Verification

The identical read script (md5 of a binary file) succeeded 4/4 after switching the path argument from `/d/Downloads/...` to `<PATH>; bash-side steps in the same pipeline kept using `/d/...` without change. Also confirmed the converse: the same Python script with the `/d/` form fails reproducibly with FileNotFoundError while `test -f` on the same string succeeds in bash.
