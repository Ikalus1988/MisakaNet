---
title: "Hand-Written OOXML PPTX: Truncation Marker Written Back, and Missing cNvPr descr"
domain: "dsh"
tags:
  - "pptx"
  - "ooxml"
  - "file-tools"
  - "truncation"
  - "powershell"
  - "xml-validation"
  - "office"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: '手写 pptx 时把工具读回来的截断标记写进了源码，报 SyntaxError；又因为图片元素缺 descr 属性，读回工具直接拒绝输出。'
trigger: "value is not lossless JSON ppt_read invalid output SyntaxError: Invalid or unexpected token line truncated to 2000 chars cNvPr descr"
verify: '补 descr 后 ppt_read 能读回 8 页全部元素及英寸坐标；对全部 30 个 part 做 [xml] 解析 invalid=0；每页越界元素合计 0'
source: "intake-3088"
provenance:
  issue: "#3088"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Two independent failures while hand-writing OOXML to produce a `.pptx`:

**1. A read → write round-trip corrupted the source.** Reading the generator source back with the agent's `tools.read` and writing it out again carried the truncation marker `(line truncated to 2000 chars)` into the saved file, so the next run failed with:

```
SyntaxError: Invalid or unexpected token
```

**2. A picture element the reader refuses.** With `<p:cNvPr>` under `<p:pic>` missing its `descr` attribute, the DSH `ppt_read` tool returned:

```
tool "ppt_read" returned invalid output: value is not lossless JSON
```

The second failure has no error code and no field name, so it reads like a tool bug rather than a defect in the generated file.

## Root Cause

**1. The truncation marker is content.** `tools.read` truncates over-long lines and appends a `(line truncated to 2000 chars)` marker so a human knows the view was clipped. Write that view back and the marker becomes literal text in the file — for the generated source that meant a string or token cut off mid-literal, hence `SyntaxError: Invalid or unexpected token`. A read → write round-trip is only an identity operation when nothing was truncated; on a file with over-long lines it is not.

**2. `descr` is what the reader needed.** The reporter's evidence is differential, not documented: comparing against the pptx the plugin itself generates showed `<p:cNvPr>` carrying `descr` where the hand-written version carried none, and adding the attribute made `ppt_read` succeed. Not given by the reporter — 报料者未给出，需复现确认: *why* `descr` specifically is required (i.e. whether it is the only attribute whose absence makes the mapping lossy, or just the first one hit).

The diagnosis path is worth keeping, because the obvious first move does not work:

1. A minimal repro built from the line content **failed** — the repro string itself was truncated, so the repro reproduced nothing.
2. A bisect probe (text only → + solid fill box → + frame/lines → + picture) narrowed the culprit to the picture element.
3. Comparing the hand-written XML against the plugin's own output found the missing `descr`.

## Solution

**1. Stop doing read → write round-trips on files with over-long lines.** Use `edit` with a short anchor, or regenerate the whole section/file. If you must rewrite, assert that the payload contains no `(line truncated` marker before saving.

**2. Give every `<p:pic>`'s `<p:cNvPr>` a `descr="..."` (alt text):**

```xml
<p:pic>
  <p:nvPicPr>
    <p:cNvPr id="4" name="Picture 3" descr="Example chart image"/>
    <p:cNvPicPr/>
    <p:nvPr/>
  </p:nvPicPr>
  <!-- p:blipFill / p:spPr follow -->
</p:pic>
```

**3. Validate the XML with PowerShell using `-Encoding UTF8` and `-LiteralPath`:**

```powershell
[xml]$x = Get-Content -LiteralPath "$dir\[Content_Types].xml" -Encoding UTF8
```

Without `-Encoding UTF8` the file is read as GBK, which produces false "illegal character" reports on legitimate UTF-8 — a validation step that lies is worse than no validation step. Without `-LiteralPath`, the brackets in `[Content_Types].xml` are treated as a wildcard character class.

## Verification

Reporter's criteria, run after adding `descr`:

- `ppt_read` reads the deck back successfully: **8 slides**, all elements, with inch coordinates — no `invalid output` error.
- `[xml]` cast over all **30 parts** → `invalid=0`.
- Colour audit: `srgbClr` values deduplicated give **exactly 4** distinct hex values (i.e. the palette is the one you meant to use, not an accidental fifth shade).
- Out-of-bounds elements, summed over slides: **0**.

The colour and bounds checks are the ones that catch silent damage: a deck can open, read back, and still be wrong. Not given by the reporter — 报料者未给出，需复现确认: whether `ppt_read` (rather than a plain `[xml]` parse) is also what a reader should trust for `sp`/`graphicFrame` elements, or only for pictures.
