---
title: "PowerShell 5.1 Set-Content -Encoding UTF8 adds a BOM that breaks an Electron app's package.json"
domain: "windows"
tags:
  - "windows"
  - "powershell"
  - "utf8-bom"
  - "encoding"
  - "electron"
  - "json-parse"
  - "package-json"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "PowerShell 5.1 的 -Encoding UTF8 会加 BOM，Electron 解析 package.json 直接报 Unexpected token；无 BOM 要用 .NET 写。"
trigger: "DesktopHostFatalError: Unexpected token is not valid JSON, Electron package.json edited with Set-Content -Encoding UTF8"
verify: "Read the first three bytes of package.json: EF BB BF means the BOM is still there; 7B (a brace) means it is gone and the app starts."
source: "intake-3839"
provenance:
  issue: "#3839"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# PowerShell 5.1 `Set-Content -Encoding UTF8` adds a BOM that breaks an Electron app's package.json

## Problem

An Electron application's `package.json` was edited with Windows PowerShell 5.1:

```powershell
Set-Content -Path <app-dir>\package.json -Value $json -Encoding UTF8
```

The file looked completely normal — `Get-Content` showed ordinary JSON, indentation intact, no
visible junk — but on the next launch the application crashed:

```
DesktopHostFatalError: Unexpected token '<U+FEFF>', "{…" is not valid JSON
```

The message contains the byte-order mark itself at the start of the quoted document, which is why it
prints as `Unexpected token ''` and looks like an empty quoted string; it is written here as
`<U+FEFF>` because the character is invisible in a terminal.

The usual suspects were tried first — JSON syntax, quoting, mixed encodings — and every attempt to
"fix the JSON" changed nothing. The clue that broke it open: both `grep` and `ConvertFrom-Json`
reported the failure at **character 1** of a document whose first character is visibly `{`.

## Root Cause

**In Windows PowerShell 5.1, `-Encoding UTF8` means UTF-8 *with* a BOM.** `Set-Content` therefore
writes the three bytes `EF BB BF` in front of the document, and `Out-File -Encoding UTF8` behaves the
same way — the reporter tried both. This is a 5.1 semantics difference: on PowerShell 7, `utf8` is
BOM-less and `utf8BOM` is the explicit opt-in.

**A BOM is not part of the JSON grammar.** The file is valid UTF-8 and, after the first three bytes,
valid JSON — but a consumer that decodes the file to a string and passes it to `JSON.parse` sees
`U+FEFF` as the document's first character and refuses it: *"Unexpected token, position 1"*. Nothing
about the JSON body is wrong, which is exactly why syntax checks, indentation and quote fixes all
came back clean and the error kept pointing at character 1.

**The symptom is invisible in the places people look.** `Get-Content` and editors silently drop or
hide a leading BOM, so "the file is fine" and "the parse fails at character 1" are both true at the
same time. The only place the BOM is visible is the byte level — or in the parser's own complaint
about the first character.

## Solution

**Write the file with an explicit BOM-less UTF-8 encoder** (the reporter's fix):

```powershell
$path = '<app-dir>\package.json'
$text = Get-Content -Raw -LiteralPath $path
[System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
```

`UTF8Encoding($false)` is the whole fix: `$false` means "do not emit a preamble". The same pattern
works for any data file a program — not PowerShell — will read.

**Do not use these on 5.1 for files consumed by other programs:**

- `Set-Content -Encoding UTF8` / `Out-File -Encoding UTF8` — both emit the BOM.
- `-Encoding ascii` — no BOM, but every non-ASCII character is mangled; safe only when the content
  is guaranteed ASCII (a `package.json` with a Chinese `description` is not).
- `pwsh` 7 with `-Encoding utf8` is BOM-less by default; `-Encoding utf8BOM` is the deliberate
  opt-in. Do not assume `pwsh` is what you are running — `$PSVersionTable.PSEdition` tells you.

**Prefer a JSON round-trip over textual surgery** when editing programmatically, so the output is
written by a serializer rather than by `Set-Content` at all:

```powershell
$obj = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
$obj.version = '<new-version>'
[System.IO.File]::WriteAllText($path, ($obj | ConvertTo-Json -Depth 20),
  (New-Object System.Text.UTF8Encoding($false)))
```

**Check the bytes after writing, not the text.**

```powershell
$b = [System.IO.File]::ReadAllBytes($path)
'{0:X2} {1:X2} {2:X2}' -f $b[0], $b[1], $b[2]
```

## Verification

The reporter's criterion: the first three bytes of the file are `7B 0D 0A` — that is `{` followed by
CRLF, the document starting immediately — and the application starts normally. The failing signature
is `EF BB BF`, the UTF-8 BOM, which must not appear whatever the line endings are.

A consumer-side check that does not depend on the app: decoding with plain `utf-8` and parsing makes
the BOM an error in its own right, which is exactly what the Electron app did —

```bash
python3 -c "import json,pathlib; json.loads(pathlib.Path('package.json').read_text('utf-8'))"
```

fails with `Unexpected UTF-8 BOM` while the content is still BOM-carrying, and passes after the
rewrite. (Reading with `utf-8-sig` hides the problem — do not use it in the check.)

## Notes

- Evidence E1: single contributor report on Windows PowerShell 5.1; the application name, its
  Electron version and the exact edit are not recorded in the intake — 报料者未给出，需复现确认
  those details if the crash must be matched exactly.
- The intake body was flagged by the L4 injection scan for invisible characters. That is the BOM
  itself travelling inside the error text; it has been replaced with `<U+FEFF>` here so the lesson
  stays free of invisible code points.
- **Opposite direction, and the advice does not transfer:**
  `lessons/contrib/powershell-51-decodes-bom-less-utf8-ps1-as-ansi.md` is about 5.1 reading a
  BOM-less `.ps1` as ANSI, where adding a BOM is the *fix*. A `.ps1` the engine must decode wants a
  BOM; a `.json` another program must parse does not. Same three bytes, opposite verdicts — decide by
  **who reads the file**, not by "UTF-8 is UTF-8".
- `ConvertFrom-Json` reporting the error at character 1 is the cheapest tell for this whole family:
  when the parser hates the first character of a file whose first character is visibly fine, suspect
  a preamble, not the body.
