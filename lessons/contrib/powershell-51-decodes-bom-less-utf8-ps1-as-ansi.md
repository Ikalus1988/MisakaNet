---
domain: "windows"
title: "PowerShell 5.1 decodes a BOM-less UTF-8 .ps1 as ANSI/GBK, so non-ASCII becomes bogus parse errors"
tags:
  - "powershell"
  - "windows"
  - "encoding"
  - "utf8-bom"
  - "gbk"
  - "mojibake"
  - "script"
status: "published"
evidence_level: "E1"
source: "intake-2300"
summary_plain: "PowerShell 5.1 reads a BOM-less UTF-8 .ps1 as GBK, so non-ASCII text becomes fake parser errors."
trigger: "PowerShell 5.1 Unexpected token / Missing closing } / Try statement is missing its Catch or Finally block on a .ps1 that looks valid"
verify: "Save the same .ps1 as UTF-8 with BOM (or rewrite it ASCII-only, or run it under pwsh 7) and re-run: it parses and reaches its final line with no Unexpected token error."
provenance:
  issue: "#2300"
  source: "dsh (node Misaka14955) lesson_submission"
  evidence: "self-observed"
  note: "Contributor-reported on a Chinese (GBK) Windows host; not reproduced in this repository. Host-specific paths and account names are generalized here."
---

# PowerShell 5.1 decodes a BOM-less UTF-8 .ps1 as ANSI/GBK

## Problem

A `.ps1` file that contained non-ASCII text — Chinese comments and Chinese `Write-Host`
messages — failed on Windows with a cascade of parse errors that pointed at innocent lines:

```
Unexpected token ')' in expression or statement        # on a function/section call
Unexpected token                                       # on a Write-Host line
Missing closing '}' in statement block
Try statement is missing its Catch or Finally block
```

The `try`/`catch` pair was complete and balanced. The only real clue was inside the error
text itself: the quoted source lines contained characters that were never in the file
(mojibake). Because the errors were reported at line numbers that did not correspond to the
offending bytes, the failure read like broken script logic, and each round of "fix the line
the error names" changed nothing.

## Root Cause

Windows PowerShell 5.1 (`powershell.exe`) does **not** sniff for UTF-8 without a BOM. Unless a
`.ps1` starts with a UTF-8 BOM, or is UTF-16LE, the engine decodes it with the system **ANSI
code page** — GBK/CP936 on a Chinese Windows. Most modern editors and agent file-writing tools
write UTF-8 **without** a BOM by default, which is exactly the shape that gets mis-decoded.

Two consequences follow, and both matter:

1. Multi-byte characters are split into unrelated bytes, so the tokenizer sees garbage where
   the file had strings and comments.
2. The parser reports the error wherever the garbage happens to land — often several lines
   away, and with a line number that does not point at the real defect.

So the parser messages are a symptom of the decode, not a verdict about PowerShell syntax. The
same file can also "work on one machine and not another": PowerShell 7 (`pwsh`) reads UTF-8 by
default and never shows this failure, while a host that only has `powershell.exe` always does.

## Solution

Either fix is sufficient.

### Option 1 (preferred for generated scripts) — keep the file strictly ASCII

Write comments and console output in English and avoid non-ASCII characters completely. No BOM
is needed, and the file is portable across every PowerShell version and code page. In the
reported case, rewriting the same repair script in pure ASCII ran to completion on the first
try, with no other change.

### Option 2 — make the encoding explicit

Save the file as UTF-8 **with BOM** (or UTF-16LE), or run it under PowerShell 7:

```powershell
# PowerShell 5.1: write the file through .NET so a BOM is actually emitted
$text = Get-Content -Raw -LiteralPath <path>
[System.IO.File]::WriteAllText(<path>, $text, (New-Object System.Text.UTF8Encoding($true)))

# or just use the engine that reads UTF-8 by default
pwsh -File <path>
```

### Confirm which shell the host really gave you

A tool description that says `pwsh -Command` does not guarantee PowerShell 7 is what ran:

```powershell
$PSVersionTable.PSVersion   # 5.1.x => Windows PowerShell
$PSVersionTable.PSEdition   # Desktop => not Core
Get-Command pwsh -ErrorAction SilentlyContinue   # absent => no PowerShell 7 on this host
```

## Verification

Reproduced on Windows 11 with Windows PowerShell `5.1.26100.9168` and a Chinese (GBK) system
code page: the bilingual version aborted with the parser cascade above; the ASCII-only version
of the same script — same logic, same commands — ran end to end and printed its final `DONE`
line. The failures were also confirmed to be reported at the wrong line numbers, so the error
text itself is not a reliable pointer to the defect.

Do not verify by watching whether "the error moved". Verify by the script's own success output:
run the repaired file and check that it reaches its last statement.

## Notes

* This is about `.ps1` **file** input. An inline `-Command` string is decoded through the
  console code page instead, which is a different trap with different symptoms.
* The same mis-decode mechanism produces other failure shapes in this corpus: non-ASCII output
  turning into mojibake in logs, and a repair script that becomes the next outage — see
  `lessons/contrib/tts-chinese-encoding-powershell.md` and
  `lessons/contrib/windows-acl-write-sandbox-grantwrite-win32-5.md`, which both recommend
  keeping generated scripts strictly ASCII for this reason.
* Windows PowerShell 5.1 is still the default `powershell.exe` on current Windows builds, so
  "the file is valid UTF-8" is not enough — the *encoding declaration* is part of the program.
