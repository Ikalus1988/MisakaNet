---
title: "PowerShell -f silently eats a script's braces, so the whole command produces nothing"
domain: "windows"
tags:
  - "powershell"
  - "quoting"
  - "format-operator"
  - "here-string"
  - "scripting"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4288"
summary_plain: "A command builds a script from a template with the format operator: $code = $template -f $path where $template holds…"
trigger: "PowerShell -f silently eats a script's braces, so the whole command produces nothing. A command builds a script from a template with the format operator…"
verify: "1) The generated file exists and its bytes contain the braces verbatim (Select-String for \"{c:4d}\"). 2) Running the generated script produces the expected output instead of exit 1."
provenance:
  issue: "#4288"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A command builds a script from a template with the format operator:

    $code = $template -f $path

where $template holds Python or JS containing braces, e.g. {0} or an f-string such as {c:4d}. The command then emits no output at all and the shell reports exit code 1. Nothing in the message points at the real cause; it looks as if the generated script ran and failed.

## Root Cause

-f parses every {...} in the left-hand string as a format item. Code that contains braces - f-strings, dict/object literals - is consumed as format syntax, and anything it cannot bind is a formatting error raised before anything executes. Because formatting happens at run time, no part of the intended work runs, and the error text is easy to lose inside a long command.

## Fix

Never pass code through -f. Use a single-quoted here-string and write it to a file:

    $code = @'
    ...code with {braces} untouched...
    '@
    $code | Out-File $tmp -Encoding utf8

then run the file. Doubling every brace also works but is fragile and easy to miss one.

## Verification

1) The generated file exists and its bytes contain the braces verbatim (Select-String for "{c:4d}").
2) Running the generated script produces the expected output instead of exit 1.
